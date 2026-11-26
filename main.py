# main.py
# Starts the DriveShare app.

import sqlite3
import os

# database file and schema file live in the same folder as this file
FOLDER = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(FOLDER, "driveshare.db")
SCHEMA_FILE = os.path.join(FOLDER, "schema_cis.sql")


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row 
    conn.execute("PRAGMA foreign_keys = ON") 
    return conn


def create_tables():
    conn = get_connection()
    exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cars'").fetchone()

    if not exists:
        with open(SCHEMA_FILE, "r") as f:
            conn.executescript(f.read())
        conn.commit()

    conn.close()


if __name__ == "__main__":
    from login_gui import App

    create_tables()

    
    App().mainloop()
