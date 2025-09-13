#!/usr/bin/env python3
"""
Database setup script for Eleven Clone application.
This script creates the necessary collections and sample data.
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME", "eleven_clone")

async def setup_database():
    """Set up the database with collections and sample data."""
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    
    try:
        print("Connecting to MongoDB...")
        
        # Create collections
        print("Creating collections...")
        
        # Audio URLs collection
        audio_urls_collection = db.audio_urls
        await audio_urls_collection.create_index("language", unique=True)
        
        # Onboarding profiles collection
        onboarding_profiles_collection = db.onboarding_profiles
        await onboarding_profiles_collection.create_index("personalDetails.email", unique=True)
        await onboarding_profiles_collection.create_index("createdAt")
        
        # Users collection
        users_collection = db.users
        await users_collection.create_index("email", unique=True)
        await users_collection.create_index("createdAt")
        
        print("Collections created successfully!")
        
        # Insert sample audio URLs
        print("Inserting sample audio URLs...")
        
        sample_audio_urls = [
            {
                "language": "english",
                "url": "https://example.com/audio/english_sample.mp3",
                "description": "English voice sample",
                "createdAt": datetime.utcnow().isoformat(),
                "updatedAt": datetime.utcnow().isoformat()
            },
            {
                "language": "arabic",
                "url": "https://example.com/audio/arabic_sample.mp3",
                "description": "Arabic voice sample",
                "createdAt": datetime.utcnow().isoformat(),
                "updatedAt": datetime.utcnow().isoformat()
            }
        ]
        
        for audio_url in sample_audio_urls:
            # Check if document already exists
            existing = await audio_urls_collection.find_one({"language": audio_url["language"]})
            if not existing:
                await audio_urls_collection.insert_one(audio_url)
                print(f"Inserted audio URL for {audio_url['language']}")
            else:
                print(f"Audio URL for {audio_url['language']} already exists")
        
        print("Sample data inserted successfully!")
        
        # Verify collections
        collections = await db.list_collection_names()
        print(f"Available collections: {collections}")
        
        # Count documents
        audio_count = await audio_urls_collection.count_documents({})
        profiles_count = await onboarding_profiles_collection.count_documents({})
        users_count = await users_collection.count_documents({})
        
        print(f"Audio URLs count: {audio_count}")
        print(f"Onboarding profiles count: {profiles_count}")
        print(f"Users count: {users_count}")
        
        print("Database setup completed successfully!")
        
    except Exception as e:
        print(f"Error setting up database: {e}")
        raise
    finally:
        client.close()

async def main():
    """Main function to run the setup."""
    await setup_database()

if __name__ == "__main__":
    asyncio.run(main())
