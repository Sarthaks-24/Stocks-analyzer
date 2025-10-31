# fetch_data.py
#Import necessary modules
import os, asyncio, json, ssl, websockets, requests
from datetime import datetime
from google.protobuf.json_format import MessageToDict
from dotenv import load_dotenv
import uuid # For unique GUIDs
import sqlite3

load_dotenv()

import MarketDataFeedV3_pb2 as pb
import create_db # Import the database creation script

# --- Configuration ---
DB_FILE = 'resources/live_data.db'


def get_market_data_feed_authorize_v3():
    """Get authorization for market data feed."""
    access_token = os.getenv('A_TOKEN')
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    url = 'https://api.upstox.com/v3/feed/market-data-feed/authorize'
    try:
        api_response = requests.get(url=url, headers=headers)
        print(f"DEBUG: Authorization response status: {api_response.status_code}")
        return api_response.json()
    except Exception as e:
        print(f"ERROR: Authorization request failed: {e}")
        return {}


def decode_protobuf(buffer):
    """Decode protobuf message."""
    feed_response = pb.FeedResponse()
    feed_response.ParseFromString(buffer)
    return feed_response

# --- Helper function for safely getting nested dictionary keys ---
def safe_get_nested(data, *keys, default=None):
    """
    Safely navigate nested dictionary structure.
    """
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
            if result is None: return default
        else: return default
    return result if result is not None else default

### -----------------------------------------------------------------
### THIS IS THE NEW "WRITE METHOD"
### -----------------------------------------------------------------
def _blocking_db_write(tick_data):
    """
    This function runs in a separate thread to avoid
    blocking the asyncio event loop.
    """
    try:
        # Connect and Insert in the same thread
        conn = sqlite3.connect(DB_FILE, timeout=10) # Add timeout
        conn.execute(
            "INSERT INTO ticks (timestamp, instrument_key, ltp, cp, oi, iv, delta, gamma, vega, theta) VALUES (?,?,?,?,?,?,?,?,?,?)",
            tick_data
        )
        conn.commit()
        conn.close()
    except sqlite3.OperationalError as e:
        print(f"ERROR: Database is locked. Failed to write tick. {e}")
    except Exception as e:
        print(f"Error in _blocking_db_write: {e}")

async def save_tick_to_db(timestamp, instrument_key, feed_dict):
    """
    Parses a *dictionary* (from MessageToDict) and inserts it 
    into the SQLite database.
    """
    try:
        # Read from the dictionary using the helper
        market_ff = safe_get_nested(feed_dict, 'fullFeed', 'marketFF', default={})
        
        # --- THIS IS THE FIX ---
        # Use standard .get() with a positional default argument, not a keyword.
        ltpc = market_ff.get('ltpc', {}) 
        greeks = market_ff.get('optionGreeks', {})
        # --- END OF FIX ---

        # Flatten the data into a tuple
        tick_data = (
            timestamp,
            instrument_key,
            float(ltpc.get('ltp', 0.0) or 0.0),
            float(ltpc.get('cp', 0.0) or 0.0),
            float(market_ff.get('oi', 0) or 0),
            float(market_ff.get('iv', 0) or 0),
            float(greeks.get('delta', 0) or 0),
            float(greeks.get('gamma', 0) or 0),
            float(greeks.get('vega', 0) or 0),
            float(greeks.get('theta', 0) or 0)
        )
        
        # Run the blocking database write in a separate thread
        await asyncio.to_thread(_blocking_db_write, tick_data)

    except Exception as e:
        print(f"Error in save_tick_to_db for {instrument_key}: {e}")
        pass


async def fetch_market_data():
    """Fetch market data using WebSocket and print it."""

    # Create default SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    # Get market data feed authorization
    response = get_market_data_feed_authorize_v3()
    
    # Check if authorization was successful
    if 'data' not in response:
        print("ERROR: Authorization failed!")
        if 'errors' in response:
            print(f"ERROR: {response['errors']}")
        else:
            print(f"ERROR: Unexpected response: {response}")
        print("Please check your access token in the .env file")
        return

    websocket_url = response["data"]["authorized_redirect_uri"]
    print(f"DEBUG: WebSocket URL: {websocket_url}")

    # Connect to the WebSocket with SSL context
    try:
        async with websockets.connect(websocket_url, ssl=ssl_context) as websocket:
            print('DEBUG: Connection established')

            await asyncio.sleep(1)  # Wait for 1 second
            
            try:
                with open('resources/instruments.txt','r') as f:
                    instruments = [line.strip() for line in f if line.strip()]
                if not instruments:
                    print("ERROR: instruments.txt is empty. Nothing to subscribe to.")
                    return
            except Exception as e:
                print(f"ERROR: Could not read 'resources/instruments.txt': {e}")
                return

            # Data to be sent over the WebSocket
            data = {
                "guid": str(uuid.uuid4()), # FIX: Generate a random, unique GUID
                "method": "sub",
                "data": {
                    "mode": "full",
                    "instrumentKeys": instruments
                }
            }

            # Convert data to binary and send over WebSocket
            binary_data = json.dumps(data).encode('utf-8')
            await websocket.send(binary_data)
            print(f"DEBUG: Subscription sent for {len(instruments)} instruments.")
            print("DEBUG: Now waiting for data from server...")

            # Continuously receive and decode data from WebSocket
            while True:
                try:
                    message = await websocket.recv()
                    decoded_data = decode_protobuf(message)
                    data_dict = MessageToDict(decoded_data) # This is your working line

                    # Get timestamp from the dictionary
                    ts_str = data_dict.get("currentTs")
                    try:
                        ts_datetime = datetime.fromtimestamp(int(ts_str) / 1000.0)
                        iso_timestamp = ts_datetime.isoformat(timespec='microseconds')
                    except Exception:
                        iso_timestamp = datetime.now().isoformat(timespec='microseconds')


                    if data_dict.get("type") == "live_feed":
                        feeds = data_dict.get("feeds", {})
                        
                        # --- THIS IS THE NEW LOGIC ---
                        # Loop through the dictionary and save each tick to the DB
                        for instrument_key, feed_data_dict in feeds.items():
                            await save_tick_to_db(iso_timestamp, instrument_key, feed_data_dict)
                        # --- END OF NEW LOGIC ---
                        
                        print(f"DEBUG: Saved {len(feeds)} ticks to DB at {iso_timestamp}")

                    elif data_dict.get("type") == "market_info":
                        print(f"Market Status Update: {data_dict.get('marketInfo', {}).get('segmentStatus')}")

                except websockets.exceptions.ConnectionClosed:
                    print("DEBUG: WebSocket connection closed")
                    break
                except Exception as e:
                    print(f"ERROR: Error receiving data: {e}")
                    break

    except Exception as e:
        print(f"ERROR: WebSocket connection failed: {e}")


if __name__ == "__main__":
    # Ensure the database file and table exist BEFORE connecting
    print("Checking database...")
    create_db.create_database()
    
    # Execute the function to fetch market data
    print("Starting market data feed...")
    asyncio.run(fetch_market_data())