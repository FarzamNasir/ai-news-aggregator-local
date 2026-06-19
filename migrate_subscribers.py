"""
Database Migration: Add subscribers and digest_sends tables.

Run this script once against the production database to create the
new tables needed for the multi-user subscriber system.

Usage:
    DATABASE_URL=postgresql://... python migrate_subscribers.py
"""

import os
import sys

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text, inspect


def run_migration():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: Set DATABASE_URL environment variable.")
        sys.exit(1)

    engine = create_engine(db_url)
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    print(f"Connected to database. Existing tables: {existing_tables}")

    with engine.begin() as conn:
        # ── Create subscribers table ─────────────────────────────
        if "subscribers" not in existing_tables:
            print("Creating 'subscribers' table...")
            conn.execute(text("""
                CREATE TABLE subscribers (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR NOT NULL,
                    email VARCHAR NOT NULL UNIQUE,
                    interests TEXT[] NOT NULL DEFAULT '{}',
                    custom_note TEXT,
                    manage_token VARCHAR NOT NULL UNIQUE,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """))
            print("  ✅ subscribers table created.")
        else:
            print("  ℹ️  subscribers table already exists.")

        # ── Create digest_sends table ────────────────────────────
        if "digest_sends" not in existing_tables:
            print("Creating 'digest_sends' table...")
            conn.execute(text("""
                CREATE TABLE digest_sends (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    subscriber_id UUID NOT NULL REFERENCES subscribers(id) ON DELETE CASCADE,
                    digest_id UUID NOT NULL REFERENCES digests(id) ON DELETE CASCADE,
                    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_subscriber_digest UNIQUE (subscriber_id, digest_id)
                );
            """))
            print("  ✅ digest_sends table created.")
        else:
            print("  ℹ️  digest_sends table already exists.")

        # ── Create indexes ───────────────────────────────────────
        print("Creating indexes...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_subscribers_email ON subscribers (email);
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_subscribers_is_active ON subscribers (is_active);
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_digest_sends_subscriber_id ON digest_sends (subscriber_id);
        """))
        print("  ✅ Indexes created.")

    print("\n✅ Migration complete!")

    # Verify
    inspector = inspect(engine)
    final_tables = inspector.get_table_names()
    print(f"Final tables: {final_tables}")


if __name__ == "__main__":
    run_migration()
