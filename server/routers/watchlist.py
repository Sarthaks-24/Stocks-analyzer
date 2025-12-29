from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_client
from config import settings
from typing import List
from datetime import date

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

class WatchlistItem(BaseModel):
    instrument_key: str
    name: str = ""
    exchange: str = ""
    segment: str = ""
    expiry: str = None  # Using string for simplicity, can parse to Date
    strike: float = 0.0

@router.get("/")
def get_watchlist():
    client = get_client()
    try:
        result = client.query(f"SELECT * FROM {settings.CLICKHOUSE_DB}.watchlist")
        # ClickHouse connect returns named tuples or list of lists
        # We should map manually or use dict cursor equivalent if available
        # result.named_results() is good
        return [dict(row) for row in result.named_results()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/")
def add_to_watchlist(item: WatchlistItem):
    client = get_client()
    try:
        # Check if exists
        exists = client.command(f"SELECT count() FROM {settings.CLICKHOUSE_DB}.watchlist WHERE instrument_key = '{item.instrument_key}'")
        if exists > 0:
            return {"message": "Already in watchlist"}
            
        # Insert
        # Date handling might need care, keep it simple for now
        client.insert(
            f"{settings.CLICKHOUSE_DB}.watchlist",
            [[item.instrument_key, item.name, item.exchange, item.segment, 
              # For date, if None pass '1970-01-01' or similar dummy
              item.expiry if item.expiry else '1970-01-01', 
              item.strike, 
              # added_at handled by default
              ]],
            column_names=['instrument_key', 'name', 'exchange', 'segment', 'expiry', 'strike']
        )
        return {"message": "Added to watchlist"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{instrument_key}")
def remove_from_watchlist(instrument_key: str):
    client = get_client()
    try:
        # Using ALTER DELETE is heavy in ClickHouse, usually we use lightweight delete
        # client.command(f"ALTER TABLE {settings.CLICKHOUSE_DB}.watchlist DELETE WHERE instrument_key = '{instrument_key}'")
        # Or standard DELETE FROM if enabled (requires mutations)
        client.command(f"DELETE FROM {settings.CLICKHOUSE_DB}.watchlist WHERE instrument_key = '{instrument_key}'")
        return {"message": "Removed from watchlist"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
