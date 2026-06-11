"""
Database Migration: Add new SourceType enum values

Run once against the production database to add the new enum values
required by the HuggingFace, Meta AI, and arXiv scrapers.

Usage:
    uv run python migrate_source_types.py
"""
import os
import sys

# Allow running without .env by passing DATABASE_URL directly
if len(sys.argv) > 1:
    os.environ["DATABASE_URL"] = sys.argv[1]

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.database.connection import engine

NEW_VALUES = ["huggingface", "meta_ai", "arxiv"]


def add_enum_values():
    print("=" * 55)
    print("  Migrating SourceType enum — adding new values")
    print("=" * 55)

    with engine.begin() as conn:
        for value in NEW_VALUES:
            # Check if value already exists to make this idempotent
            result = conn.execute(
                text(
                    "SELECT EXISTS ("
                    "  SELECT 1 FROM pg_enum e"
                    "  JOIN pg_type t ON t.oid = e.enumtypid"
                    "  WHERE t.typname = 'sourcetype'"
                    "  AND e.enumlabel = :value"
                    ")"
                ),
                {"value": value},
            )
            already_exists = result.scalar()

            if already_exists:
                print(f"  [SKIP] '{value}' already exists in enum")
            else:
                conn.execute(
                    text(f"ALTER TYPE sourcetype ADD VALUE '{value}'")
                )
                print(f"  [OK]   Added '{value}' to sourcetype enum")

    print()
    print("  Migration complete!")
    print("=" * 55)


if __name__ == "__main__":
    add_enum_values()
