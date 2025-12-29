import asyncio
import socketio
import json
import logging
from datetime import datetime
import clickhouse_connect
from config import settings
from database import get_client, init_db

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Ingestor")

# XTS Market Data Configuration
# NOTE: User provided Interactive docs, but this is the standard Market Data Endpoint pattern.
# We might need to adjust URL based on specific broker environment (Live/Sim).
BASE_URL = settings.XTS_BASE_URL
MARKET_DATA_PATH = "/marketdata/socket.io" 

# ClickHouse Client
ch_client = get_client()

# SocketIO Client
# XTS uses standard engineio/socketio
sio = socketio.AsyncClient(ssl_verify=False)

# Buffer for Batch Insert
TICK_BUFFER = []
BATCH_SIZE = 5000
LAST_FLUSH_TIME = datetime.now()
FLUSH_INTERVAL_SECONDS = 1

async def flush_buffer():
    """Flushes the tick buffer to ClickHouse."""
    global TICK_BUFFER, LAST_FLUSH_TIME
    
    if not TICK_BUFFER:
        return

    try:
        # Prepare data for ClickHouse
        # Schema: timestamp, exchange_segment, exchange_instrument_id, ltp, ...
        # We need to map the incoming JSON to the table columns
        
        # Example XTS Market Data Packet (Assumed Structure based on standard XTS):
        # { "exchangeSegment": 1, "exchangeInstrumentID": 2885, "ltp": 1200.50, ... }
        
        data_to_insert = []
        for tick in TICK_BUFFER:
             # Basic mapping - needs adjustment based on exact JSON payload
            row = (
                datetime.now(), # timestamp (or tick['exchangeTimeStamp'])
                str(tick.get('ExchangeSegment', 'NSECM')),
                int(tick.get('ExchangeInstrumentID', 0)),
                float(tick.get('LastTradedPrice', 0.0)),
                int(tick.get('LastTradedQunatity', 0)), # Note: Typo 'Qunatity' is common in some XTS versions
                float(tick.get('Open', 0.0)),
                float(tick.get('High', 0.0)),
                float(tick.get('Low', 0.0)),
                float(tick.get('Close', 0.0)),
                int(tick.get('TotalTradedQuantity', 0)),
                int(tick.get('OpenInterest', 0)),
                0, # oi_change
                float(tick.get('BidPrice', 0.0)),
                float(tick.get('AskPrice', 0.0)),
                datetime.now() # inserted_at
            )
            data_to_insert.append(row)

        ch_client.insert(
            f"{settings.CLICKHOUSE_DB}.market_ticks",
            data_to_insert,
            column_names=[
                'timestamp', 'exchange_segment', 'exchange_instrument_id', 
                'ltp', 'ltp_qty', 'open', 'high', 'low', 'close', 
                'volume', 'oi', 'oi_change', 'bid_price', 'ask_price', 'inserted_at'
            ]
        )
        
        logger.info(f"Flushed {len(data_to_insert)} ticks to ClickHouse.")
        TICK_BUFFER = []
        LAST_FLUSH_TIME = datetime.now()
        
    except Exception as e:
        logger.error(f"Error flushing batch: {e}")

@sio.event
async def connect():
    logger.info("Connected to XTS Market Data Socket!")
    # TODO: Send Subscription Request here
    # await sio.emit('subscribe', {'instruments': [...]})

@sio.event
async def disconnect():
    logger.warning("Disconnected from XTS.")

@sio.on('1501-json-full') # Topic for Level 1 JSON data
async def on_market_data(data):
    """
    Handles incoming market data ticks.
    """
    global TICK_BUFFER
    # Data might be a JSON string or dict
    if isinstance(data, str):
        data = json.loads(data)
    
    # Add to buffer
    TICK_BUFFER.append(data)
    
    # Check flush conditions
    if len(TICK_BUFFER) >= BATCH_SIZE or (datetime.now() - LAST_FLUSH_TIME).total_seconds() > FLUSH_INTERVAL_SECONDS:
        await flush_buffer()


import requests
import ssl

async def main():
    # Connect to DB
    logger.info("Initializing Ingestion Service...")
    init_db()
    
    # --- AUTHENTICATION FLOW ---
    logger.info("Authenticating with XTS Market Data API...")
    
    # 1. Authorize to get WebSocket URL
    # Using User's provided Access Token
    if not settings.XTS_ACCESS_TOKEN:
        logger.error("XTS_ACCESS_TOKEN is missing in .env! Please set it.")
        return

    auth_url = f"{settings.XTS_BASE_URL}/apimarketdata/marketData/v3/authorize"
    # Note: Legacy code used /v3/feed/market-data-feed/authorize, user docs might vary?
    # Trying the standard one from legacy:
    # url = 'https://api.upstox.com/v3/feed/market-data-feed/authorize' -- Wait, legacy code was Upstox??
    # User said "Legacy V1: MarketDataFeedV3.proto" and "XTS ClickHouse Migration".
    # Wait, the `fetch_data.py` viewed earlier had `url = 'https://api.upstox.com/v3/feed/market-data-feed/authorize'`
    # BUT the User Request is clearly XTS: `https://developers.symphonyfintech.in`
    # The user provided documentation for `POST /search/instrumentsbyid` on `https://developers.symphonyfintech.in`.
    # AND `ingestor.py` initially had `XTS_BASE_URL=https://developers.symphonyfintech.in`.
    # The legacy code might have been Upstox, but the NEW system is XTS.
    
    # XTS Market Data Socket usually doesn't need a separate "authorize" call returning a redirect URI like Upstox.
    # XTS usually connects directly to socket.io with `?token=...`.
    # However, if the user insists on "Access Token", XTS has `POST /interactive/user/session` or similar.
    # The `ingestor.py` I wrote earlier uses `?token={XTS_API_KEY}`. 
    # If the user has an "Access Token", they probably mean the token from login.
    # XTS Socket connection: `http://{host}:{port}/?token={accessToken}`.
    # So I should just replace API Key with Access Token in the query param.
    
    connect_url = f"{BASE_URL}?token={settings.XTS_ACCESS_TOKEN}&userID=DATE&publishFormat=JSON"
    logger.info(f"Connecting to {BASE_URL} with Access Token...")

    # Fetch Instruments from DB
    try:
        client = get_client()
        result = client.query(f"SELECT instrument_key FROM {settings.CLICKHOUSE_DB}.watchlist")
        instruments = [row[0] for row in result.result_set]
        logger.info(f"Loaded {len(instruments)} instruments from Watchlist: {instruments}")
    except Exception as e:
        logger.error(f"Failed to load watchlist: {e}")
        instruments = []

    if not instruments:
        logger.warning("No instruments in watchlist. Waiting...")
    
    # Connect and Subscribe
    try:
        await sio.connect(
            BASE_URL, 
            socketio_path=MARKET_DATA_PATH, 
            transports=['websocket'],
            auth={'token': settings.XTS_ACCESS_TOKEN, 'userID': 'DATE', 'publishFormat': 'JSON'}
        )
        
        # Subscribe
        if instruments:
           subscription_payload = {
               "action": "subscribe", 
               "mode": "full",
               "exchangeSegmentList": instruments
           }
           await sio.emit('subscribe', subscription_payload) # Guessing event name
           
        await sio.wait()
    except Exception as e:
        logger.error(f"Connection Failed: {e}") 


if __name__ == "__main__":
    asyncio.run(main())
