#!/usr/bin/env python3
"""
Initialize SQLite database for database.

CHANGES (2026-01-28):
- Added an idempotent initializer for the application's `tasks` table.
- The tasks table uses UTC ISO 8601 timestamps for created_at/updated_at.
- Existing sample tables (app_info, users) are preserved and left intact.
- Script remains safe to execute multiple times without destructive operations.
"""

import os
import sqlite3
from datetime import datetime, timezone

DB_NAME = "myapp.db"
DB_USER = "kaviasqlite"  # Not used for SQLite, but kept for consistency
DB_PASSWORD = "kaviadefaultpassword"  # Not used for SQLite, but kept for consistency
DB_PORT = "5000"  # Not used for SQLite, but kept for consistency


def utc_now_iso8601() -> str:
    """Return current UTC time in ISO 8601 format with 'Z' suffix."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def tasks_table_ddl() -> str:
    """
    Return DDL for the tasks table.

    Schema requirement:
      tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        notes TEXT NULL,
        completed INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      )

    Notes:
    - created_at and updated_at are stored as TEXT containing UTC ISO-8601 timestamps (e.g. 2026-01-28T12:34:56Z).
    - `completed` is stored as 0/1 integer.
    """
    return """
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        notes TEXT NULL,
        completed INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """


# PUBLIC_INTERFACE
def ensure_schema(conn: sqlite3.Connection) -> None:
    """
    Ensure required database schema exists (idempotent).

    This function is safe to run multiple times. It will create missing tables,
    and it will not drop or truncate any existing data.
    """
    cursor = conn.cursor()

    # Keep existing sample tables for safety/backwards-compatibility.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS app_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Required table for the to-do app.
    cursor.execute(tasks_table_ddl())

    # Optional but helpful index for common reads (safe / non-destructive).
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at)")

    conn.commit()


def main() -> None:
    """Create/open SQLite DB and ensure the schema exists; write helper connection files."""
    print("Starting SQLite setup...")

    # Check if database already exists
    db_exists = os.path.exists(DB_NAME)
    if db_exists:
        print(f"SQLite database already exists at {DB_NAME}")
        # Verify it's accessible
        try:
            conn = sqlite3.connect(DB_NAME)
            conn.execute("SELECT 1")
            conn.close()
            print("Database is accessible and working.")
        except Exception as e:
            print(f"Warning: Database exists but may be corrupted: {e}")
    else:
        print("Creating new SQLite database...")

    # Create database / connect
    conn = sqlite3.connect(DB_NAME)
    try:
        # Enable foreign keys (safe; no-op if unused)
        conn.execute("PRAGMA foreign_keys = ON")

        # Ensure schema exists (idempotent)
        ensure_schema(conn)

        # Insert/refresh minimal app metadata (idempotent)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
            ("project_name", "database"),
        )
        cursor.execute(
            "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
            ("version", "0.1.0"),
        )
        cursor.execute(
            "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
            ("author", "John Doe"),
        )
        cursor.execute(
            "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
            ("description", ""),
        )
        conn.commit()

        # (Non-destructive) Sanity check for tasks timestamps convention: nothing to modify,
        # but this documents expected format for future inserts/updates.
        _ = utc_now_iso8601()

        # Get database statistics
        cursor.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        table_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM app_info")
        record_count = cursor.fetchone()[0]

    finally:
        conn.close()

    # Save connection information to a file
    current_dir = os.getcwd()
    connection_string = f"sqlite:///{current_dir}/{DB_NAME}"

    try:
        with open("db_connection.txt", "w") as f:
            f.write("# SQLite connection methods:\n")
            f.write(f"# Python: sqlite3.connect('{DB_NAME}')\n")
            f.write(f"# Connection string: {connection_string}\n")
            f.write(f"# File path: {current_dir}/{DB_NAME}\n")
        print("Connection information saved to db_connection.txt")
    except Exception as e:
        print(f"Warning: Could not save connection info: {e}")

    # Create environment variables file for Node.js viewer
    db_path = os.path.abspath(DB_NAME)

    # Ensure db_visualizer directory exists
    if not os.path.exists("db_visualizer"):
        os.makedirs("db_visualizer", exist_ok=True)
        print("Created db_visualizer directory")

    try:
        with open("db_visualizer/sqlite.env", "w") as f:
            f.write(f'export SQLITE_DB="{db_path}"\n')
        print("Environment variables saved to db_visualizer/sqlite.env")
    except Exception as e:
        print(f"Warning: Could not save environment variables: {e}")

    print("\nSQLite setup complete!")
    print(f"Database: {DB_NAME}")
    print(f"Location: {current_dir}/{DB_NAME}")
    print("")

    print("To use with Node.js viewer, run: source db_visualizer/sqlite.env")

    print("\nTo connect to the database, use one of the following methods:")
    print(f"1. Python: sqlite3.connect('{DB_NAME}')")
    print(f"2. Connection string: {connection_string}")
    print(f"3. Direct file access: {current_dir}/{DB_NAME}")
    print("")

    print("Database statistics:")
    print(f"  Tables: {table_count}")
    print(f"  App info records: {record_count}")

    # If sqlite3 CLI is available, show how to use it
    try:
        import subprocess

        result = subprocess.run(["which", "sqlite3"], capture_output=True, text=True)
        if result.returncode == 0:
            print("")
            print("SQLite CLI is available. You can also use:")
            print(f"  sqlite3 {DB_NAME}")
    except Exception:
        pass

    # Exit successfully
    print("\nScript completed successfully.")


if __name__ == "__main__":
    main()
