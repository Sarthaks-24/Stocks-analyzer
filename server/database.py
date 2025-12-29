import clickhouse_connect
from config import settings
import time

def get_client():
    """Returns a ClickHouse client instance."""
    return clickhouse_connect.get_client(
        host=settings.CLICKHOUSE_HOST,
        port=settings.CLICKHOUSE_PORT,
        username='default',
        password=settings.CLICKHOUSE_PASSWORD,
        database=settings.CLICKHOUSE_DB
    )

def init_db():
    """Initializes the ClickHouse database and tables."""
    max_retries = 10
    for i in range(max_retries):
        try:
            client = clickhouse_connect.get_client(
                host=settings.CLICKHOUSE_HOST,
                port=settings.CLICKHOUSE_PORT,
                username='default',
                password=settings.CLICKHOUSE_PASSWORD
            )
            break
        except Exception as e:
            if i == max_retries - 1:
                raise e
            print(f"Waiting for ClickHouse... ({i+1}/{max_retries})")
            time.sleep(2)
    
    # Create Database
    client.command(f"CREATE DATABASE IF NOT EXISTS {settings.CLICKHOUSE_DB}")
    
    # Create Ticks Table
    # Optimized for high-frequency inserts and time-series queries
    # Partitioning by YYYYMMDD keeps parts manageable
    client.command(f"""
        CREATE TABLE IF NOT EXISTS {settings.CLICKHOUSE_DB}.market_ticks (
            timestamp DateTime64(3),
            exchange_segment LowCardinality(String),
            exchange_instrument_id UInt32,
            ltp Float32,
            ltp_qty UInt32,
            open Float32,
            high Float32,
            low Float32,
            close Float32,
            volume UInt64,
            oi UInt64,
            oi_change Int64,
            bid_price Float32,
            ask_price Float32,
            inserted_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMMDD(timestamp)
        ORDER BY (exchange_segment, exchange_instrument_id, timestamp)
        TTL timestamp + INTERVAL 7 DAY
    """);
    
    # Create Watchlist Table
    client.command(f"""
        CREATE TABLE IF NOT EXISTS {settings.CLICKHOUSE_DB}.watchlist (
            instrument_key String,
            name String,
            exchange String,
            segment String,
            expiry Date,
            strike Float32,
            added_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (exchange, segment, instrument_key)
    """)
    
    print("Database and Tables (including Watchlist) Initialized!")

if __name__ == "__main__":
    init_db()
