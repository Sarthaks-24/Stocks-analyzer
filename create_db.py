# create_db.py
import sqlite3
import os

DB_FILE = 'resources/live_data.db'

def create_database():
    
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE) 
        cursor = conn.cursor()

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

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_instrument_time
            ON ticks (instrument_key, timestamp)
        ''')

        conn.commit()

    except Exception as e:
        print(f"Error during database check/creation: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Running database setup...")
    create_database()
    print("Setup complete. You can now run fetch_data.py")