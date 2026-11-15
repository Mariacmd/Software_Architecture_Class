# database.py
# Connects to the DriveShare database and creates the tables from schema_cis.sql.
# Everyone imports get_connection() from here so we all use the same database file.

import sqlite3
import os

# Database file and schema file live in the same folder as this file
FOLDER = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(FOLDER, "driveshare.db")
SCHEMA_FILE = os.path.join(FOLDER, "schema_cis.sql")


def get_connection():
    # Opens the database. Creates the file if it doesn't exist yet.
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row          # lets us get columns by name, ex. row["make"]
    conn.execute("PRAGMA foreign_keys = ON")  # makes the links between tables actually work
    return conn


def create_tables():
    # Runs the schema file to build all the tables.
    # Only creates them if the cars table isn't there yet, so it's safe to call every time the app starts.
    conn = get_connection()
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='cars'"
    ).fetchone()

    if not exists:
        with open(SCHEMA_FILE, "r") as f:
            conn.executescript(f.read())
        conn.commit()

    conn.close()
