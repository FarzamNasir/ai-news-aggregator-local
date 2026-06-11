"""
Fix: Add UPPERCASE enum values to match what SQLAlchemy sends.

SQLAlchemy uses enum .name (HUGGINGFACE, META_AI, ARXIV) not .value
(huggingface, meta_ai, arxiv) when inserting into Postgres native enums.
The original migration added lowercase values, which don't match.

This script adds the uppercase versions. The stale lowercase ones are
harmless (Postgres ignores unused enum values).

Usage:
    uv run python fix_enum_casing.py
"""
import os
import sys

if len(sys.argv) > 1:
    os.environ["DATABASE_URL"] = sys.argv[1]

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.database.connection import engine

# SQLAlchemy sends enum NAME (uppercase), not VALUE (lowercase)
NEW_VALUES = ["HUGGINGFACE", "META_AI", "ARXIV"]


def fix_enum_casing():
    print("=" * 55)
    print("  Fixing SourceType enum — adding UPPERCASE values")
    print("=" * 55)

    with engine.begin() as conn:
        for value in NEW_VALUES:
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
                print(f"  [SKIP] '{value}' already exists")
            else:
                conn.execute(
                    text(f"ALTER TYPE sourcetype ADD VALUE '{value}'")
                )
                print(f"  [OK]   Added '{value}' to sourcetype enum")

    # Verify final state
    print()
    rows = conn.execute(text(
        "SELECT enumlabel FROM pg_enum e "
        "JOIN pg_type t ON t.oid = e.enumtypid "
        "WHERE t.typname = 'sourcetype' "
        "ORDER BY e.enumsortorder"
    ))
    print("  Final enum values:")
    for row in rows:
        print(f"    '{row[0]}'")

    print()
    print("  Fix complete!")
    print("=" * 55)


if __name__ == "__main__":
    fix_enum_casing()
