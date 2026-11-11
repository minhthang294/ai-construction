"""Create the first admin from environment variables, never from source defaults."""

import os
from sqlalchemy import select

from .auth import password_hash
from .database import SessionLocal
from .models import User


def main():
    username = os.getenv("BOOTSTRAP_ADMIN_USER")
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
    if not username or not password or len(password) < 12:
        raise SystemExit("Set BOOTSTRAP_ADMIN_USER and BOOTSTRAP_ADMIN_PASSWORD (12+ characters)")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == username)):
            raise SystemExit("Admin user already exists")
        db.add(User(username=username, password_hash=password_hash(password), role="admin"))
        db.commit()
    print("Admin user created")


if __name__ == "__main__":
    main()
