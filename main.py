from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from typing import Optional
from datetime import datetime, timedelta
import bcrypt
import os
from dotenv import load_dotenv
import uvicorn
from jose import JWTError, jwt

# Load environment variables
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME", "eleven_clone")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Initialize FastAPI app
app = FastAPI(
    title="Eleven Clone API",
    description="Backend API for ElevenLabs clone application with MongoDB authentication",
    version="1.0.0"
)

# Get CORS origins from environment variable
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# DB connection lifecycle
# ---------------------------
@app.on_event("startup")
async def startup_db_client():
    app.state.client = AsyncIOMotorClient(MONGODB_URL)
    app.state.db = app.state.client[DATABASE_NAME]
    print("✅ Connected to MongoDB")

@app.on_event("shutdown")
async def shutdown_db_client():
    app.state.client.close()
    print("❌ Disconnected from MongoDB")

# ---------------------------
# MODELS
# ---------------------------
class AudioResponse(BaseModel):
    language: str
    audioUrl: str
    createdAt: str
    updatedAt: str

class PersonalDetails(BaseModel):
    name: str
    age: int
    email: EmailStr

class OnboardingData(BaseModel):
    theme: str
    personalDetails: PersonalDetails
    referralSource: str
    persona: str
    pricingPlan: str

class OnboardingResponse(BaseModel):
    message: str
    userId: str
    status: str

class UserSignup(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    name: str
    email: str

# ---------------------------
# JWT UTILITIES
# ---------------------------
security = HTTPBearer()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), request: Request = None):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    db = request.app.state.db
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise credentials_exception
    return user

# ---------------------------
# ROOT + HEALTH
# ---------------------------
@app.get("/")
async def root():
    return {"message": "Eleven Clone API is running!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# ---------------------------
# AUDIO ROUTES
# ---------------------------
@app.get("/api/audio", response_model=AudioResponse)
async def get_audio_url(request: Request, lang: str = Query(..., description="Language code (e.g., 'english')")):
    db = request.app.state.db
    audio_doc = await db.audio_urls.find_one({"language": lang.lower()})
    if not audio_doc:
        raise HTTPException(status_code=404, detail=f"Audio URL not found for language: {lang}")

    return AudioResponse(
        language=audio_doc["language"],
        audioUrl=audio_doc["url"],
        createdAt=audio_doc.get("createdAt", ""),
        updatedAt=audio_doc.get("updatedAt", "")
    )

# ---------------------------
# ONBOARDING ROUTES
# ---------------------------
@app.post("/api/onboarding", response_model=OnboardingResponse)
async def create_onboarding_profile(request: Request, data: OnboardingData):
    db = request.app.state.db
    profile_doc = {
        "theme": data.theme,
        "personalDetails": {
            "name": data.personalDetails.name,
            "age": data.personalDetails.age,
            "email": data.personalDetails.email
        },
        "referralSource": data.referralSource,
        "persona": data.persona,
        "pricingPlan": data.pricingPlan,
        "createdAt": datetime.utcnow().isoformat(),
        "updatedAt": datetime.utcnow().isoformat()
    }

    result = await db.onboarding_profiles.insert_one(profile_doc)

    return OnboardingResponse(
        message="Onboarding profile created successfully",
        userId=str(result.inserted_id),
        status="success"
    )

@app.get("/api/onboarding/{user_id}")
async def get_onboarding_profile(request: Request, user_id: str):
    db = request.app.state.db
    profile = await db.onboarding_profiles.find_one({"_id": ObjectId(user_id)})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile["_id"] = str(profile["_id"])
    return profile

# ---------------------------
# AUTH ROUTES
# ---------------------------
@app.post("/api/auth/signup")
async def signup(user: UserSignup, request: Request):
    db = request.app.state.db
    existing = await db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed_pw = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt())

    user_doc = {
        "email": user.email,
        "name": user.name,
        "password": hashed_pw.decode("utf-8"),
        "createdAt": datetime.utcnow(),
    }
    result = await db.users.insert_one(user_doc)

    return {"message": "User created successfully", "userId": str(result.inserted_id)}

@app.post("/api/auth/login", response_model=Token)
async def login(user: UserLogin, request: Request):
    db = request.app.state.db
    user_doc = await db.users.find_one({"email": user.email})
    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not bcrypt.checkpw(user.password.encode("utf-8"), user_doc["password"].encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token_expires = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user_doc["_id"])}, expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=str(user_doc["_id"]),
        name=user_doc["name"],
        email=user_doc["email"]
    )

# ---------------------------
# MAIN ENTRY
# ---------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
