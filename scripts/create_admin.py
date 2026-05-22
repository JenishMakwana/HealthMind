"""
Run this once to create the first admin user.

Usage:
  python scripts/create_admin.py --email admin@hospital.com --password secret123 --name "Dr. Admin"
"""
import asyncio
import argparse
import uuid
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import init_db, AsyncSessionLocal, User
from app.core.security import hash_password
from sqlalchemy import select


async def create_admin(email: str, password: str, name: str):
    await init_db()
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"[!] User {email} already exists.")
            return

        user = User(
            id=str(uuid.uuid4()),
            email=email,
            hashed_password=hash_password(password),
            full_name=name,
            role="admin",
            is_active=True,
        )
        db.add(user)
        await db.commit()
        print(f"[✓] Admin created: {email} (id={user.id})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="Administrator")
    args = parser.parse_args()
    asyncio.run(create_admin(args.email, args.password, args.name))
