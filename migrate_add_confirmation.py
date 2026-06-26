"""
Migration: Add confirmation_token and confirmed_at columns to subscribers table.

Run with:
  uv run python migrate_add_confirmation.py <DATABASE_URL>

Example:
  uv run python migrate_add_confirmation.py "postgresql://user:pass@host/db"

This adds the email confirmation columns and updates existing subscribers
to be treated as already confirmed (they signed up before confirmation
was required).
"""

import sys
from sqlalchemy import create_engine, text

if len(sys.argv) < 2:
    print("Usage: uv run python migrate_add_confirmation.py <DATABASE_URL>")
    sys.exit(1)

DATABASE_URL = sys.argv[1]
engine = create_engine(DATABASE_URL)

with engine.begin() as conn:
    # 1. Add confirmation_token column (nullable, unique)
    try:
        conn.execute(text(
            "ALTER TABLE subscribers ADD COLUMN confirmation_token VARCHAR UNIQUE"
        ))
        print("Added: confirmation_token column")
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
            print("Skipped: confirmation_token already exists")
        else:
            raise

    # 2. Add confirmed_at column (nullable timestamp)
    try:
        conn.execute(text(
            "ALTER TABLE subscribers ADD COLUMN confirmed_at TIMESTAMPTZ"
        ))
        print("Added: confirmed_at column")
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
            print("Skipped: confirmed_at already exists")
        else:
            raise

    # 3. Mark all existing active subscribers as confirmed
    #    (they signed up before the confirmation flow existed)
    result = conn.execute(text(
        "UPDATE subscribers SET confirmed_at = NOW() "
        "WHERE is_active = true AND confirmed_at IS NULL"
    ))
    print(f"Updated: {result.rowcount} existing subscribers marked as confirmed")

print("\nMigration complete!")
