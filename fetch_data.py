# fetch_data.py (Resilient Edition)
import os, asyncio, json, ssl, websockets, requests
from datetime import datetime
from google.protobuf.json_format import MessageToDict
from dotenv import load_dotenv
import uuid # For unique GUIDs
import sqlite3
import time # <-- FIX: Import time for sleeping

load_dotenv()

import MarketDataFeedV3_pb2 as pb
import create_db # Import the database creation script

# --- Configuration ---
DB_FILE = 'resources/live_data.db'
RECONNECT_DELAY_SECONDS = 10 # <-- FIX: Wait 10 seconds before retrying


def get_market_data_feed_authorize_v3():
    """Get authorization for market data feed."""
    access_token = os.getenv('A_TOKEN')
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    url = 'https://api.upstox.com/v3/feed/market-data-feed/authorize'
    try:
        # NOTE: If you are behind a proxy, you MUST add the 'proxies' argument
        # my_proxies = { "https": "http://your-proxy.com:port" }
        # api_response = requests.get(url=url, headers=headers, proxies=my_proxies)
        
        api_response = requests.get(url=url, headers=headers)
        
        print(f"DEBUG: Authorization response status: {api_response.status_code}")
        api_response.raise_for_status() # <-- FIX: Raise error on bad status (like 401)
        return api_response.json()
    except requests.exceptions.HTTPError as he:
        print(f"ERROR: HTTP Error during authorization: {he}")
        print(f"Response body: {api_response.text} (Check your A_TOKEN)")
    except Exception as e:
        print(f"ERROR: Authorization request failed: {e}")
    return {} # Return empty dict on failure


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

def _blocking_db_write(tick_data):
    """
    This function runs in a separate thread to avoid
    blocking the asyncio event loop.
    """
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10) 
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
        market_ff = safe_get_nested(feed_dict, 'fullFeed', 'marketFF', default={})
        ltpc = market_ff.get('ltpc', {}) 
        greeks = market_ff.get('optionGreeks', {})

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
    
    # --- FIX: Improved authorization check ---
    if 'data' not in response or 'authorized_redirect_uri' not in response.get('data', {}):
        print("ERROR: Authorization failed! Check .env token or proxy settings.")
        print(f"ERROR: Unexpected response: {response}")
        # Raise an exception to trigger the reconnect loop
        raise Exception("Authorization failed, will retry...") 

    websocket_url = response["data"]["authorized_redirect_uri"]
    print(f"DEBUG: WebSocket URL: {websocket_url}")

    # Connect to the WebSocket with SSL context
    # This 'async with' block is now INSIDE the retry loop
    try:
        async with websockets.connect(websocket_url, ssl=ssl_context) as websocket:
            print('DEBUG: Connection established')

            await asyncio.sleep(1)
            
            try:
                with open('resources/instruments.txt','r') as f:
                    instruments = [line.strip() for line in f if line.strip()]
                if not instruments:
                    print("ERROR: instruments.txt is empty. Nothing to subscribe to.")
                    return # This is a fatal error, so we return
            except Exception as e:
                print(f"ERROR: Could not read 'resources/instruments.txt': {e}")
                return # This is also fatal

            data = {
                "guid": str(uuid.uuid4()),
                "method": "sub",
                "data": {
                    "mode": "full",
                    "instrumentKeys": instruments
                }
            }

            binary_data = json.dumps(data).encode('utf-8')
            await websocket.send(binary_data)
            print(f"DEBUG: Subscription sent for {len(instruments)} instruments.")
            print("DEBUG: Now waiting for data from server...")

            # This is the inner loop for receiving data
            while True:
                message = await websocket.recv()
                decoded_data = decode_protobuf(message)
                data_dict = MessageToDict(decoded_data)

                ts_str = data_dict.get("currentTs")
                try:
                    ts_datetime = datetime.fromtimestamp(int(ts_str) / 1000.0)
                    iso_timestamp = ts_datetime.isoformat(timespec='microseconds')
                except Exception:
                    iso_timestamp = datetime.now().isoformat(timespec='microseconds')


                if data_dict.get("type") == "live_feed":
                    feeds = data_dict.get("feeds", {})
                    for instrument_key, feed_data_dict in feeds.items():
                        await save_tick_to_db(iso_timestamp, instrument_key, feed_data_dict)
                    
                    print(f"DEBUG: Saved {len(feeds)} ticks to DB at {iso_timestamp}")

                elif data_dict.get("type") == "market_info":
                    print(f"Market Status Update: {data_dict.get('marketInfo', {}).get('segmentStatus')}")
    
    # --- FIX: These exceptions will now be caught by the *outer* loop ---
    except websockets.exceptions.ConnectionClosed as e:
        print(f"DEBUG: WebSocket connection closed: {e}. Reconnecting...")
    except Exception as e:
        print(f"ERROR: An error occurred in fetch_market_data: {e}. Reconnecting...")
        # Raise the exception again to be caught by the outer loop
        raise e


if __name__ == "__main__":
    print("Checking database...")
    create_db.create_database()
    
    print("Starting market data feed...")
    
    # --- THIS IS THE NEW OUTER RETRY LOOP ---
    while True:
        try:
            # Run the main async function
            asyncio.run(fetch_market_data())
            
            # If asyncio.run finishes, it means a disconnect happened.
            print(f"INFO: Main loop exited. Waiting {RECONNECT_DELAY_SECONDS}s to reconnect...")
            time.sleep(RECONNECT_DELAY_SECONDS)
            
        except Exception as e:
            # This catches any unhandled error (like Auth fail)
            print(f"FATAL: Unhandled error in main loop: {e}. Retrying in {RECONNECT_DELAY_SECONDS}s...")
            time.sleep(RECONNECT_DELAY_SECONDS)