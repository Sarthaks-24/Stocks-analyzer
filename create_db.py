# create_db.py
import sqlite3
import os

DB_FILE = 'resources/live_data.db'

def create_database():
    """
    Connects to the DB (creates it if_not_exists) and
    ENSURES the 'ticks' table and index exist.
    This is safe to run every time.
    """
    conn = None
    try:
        # This will create the file if it doesn't exist
        conn = sqlite3.connect(DB_FILE) 
        cursor = conn.cursor()

        # Create the main table to hold all tick data
        # This command is ignored if the table already exists.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticks (
                timestamp TEXT,
                instrument_key TEXT,
                ltp REAL,
                cp REAL,  -- Close Price (for Chg %)
                oi REAL,
                iv REAL,
                delta REAL,
                gamma REAL,
                vega REAL,
                theta REAL
            )
        ''')

        # Create the index
        # This command is ignored if the index already exists.
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_instrument_time
            ON ticks (instrument_key, timestamp)
        ''')

        conn.commit()
        # print("Database and table verified successfully.") # Make it silent

    except Exception as e:
        print(f"Error during database check/creation: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Running database setup...")
    create_database()
    print("Setup complete. You can now run fetch_data.py")