"""
Initialize database for EDI POC
Run this script to create the database tables
"""
import asyncio
from src.database import init_database

async def main():
    """Initialize database with all tables"""
    print("Initializing database...")
    await init_database()
    print("Database initialized successfully!")

if __name__ == "__main__":
    asyncio.run(main())