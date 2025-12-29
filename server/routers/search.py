from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import requests
from config import settings
from typing import List, Optional

router = APIRouter(prefix="/search", tags=["search"])

class Instrument(BaseModel):
    instrument_key: Optional[str] = None
    exchange: Optional[str] = None
    segment: Optional[str] = None
    name: Optional[str] = None
    trading_symbol: Optional[str] = None
    expiry: Optional[str] = None
    strike: Optional[float] = None
    lot_size: Optional[int] = None
    tick_size: Optional[float] = None

@router.post("/instrumentsbyid")
async def search_instruments_by_id(
    source: str = "WebAPI",
    userID: str = "guest",
    instruments: List[dict] = []
):
    """
    Proxy for XTS POST /search/instrumentsbyid
    """
    url = f"{settings.XTS_BASE_URL}/apimarketdata/search/instrumentsbyid"
    payload = {
        "source": source,
        "UserID": userID,
        "instruments": instruments
    }
    
    try:
        response = requests.post(url, json=payload)
        # For development/demo if API fails or needs auth we might need to handle it
        # But assuming public search doesn't need heavy auth based on doc snippet
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/instruments")
async def search_instruments(searchString: str, source: str = "WEB"):
    """
    Proxy for XTS GET /search/instruments
    """
    url = f"{settings.XTS_BASE_URL}/apimarketdata/search/instruments"
    params = {
        "searchString": searchString,
        "source": source
    }
    
    try:
        headers = {'Authorization': settings.XTS_ACCESS_TOKEN}
        response = requests.get(url, params=params, headers=headers)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
