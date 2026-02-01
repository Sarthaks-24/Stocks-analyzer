from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # XTS Config (Market Data)
    XTS_API_KEY: str = ""
    XTS_API_SECRET: str = ""
    XTS_ACCESS_TOKEN: str = "" # Added for real auth flow
    XTS_BASE_URL: str = "https://developers.symphonyfintech.in"
    
    # ClickHouse Config
    CLICKHOUSE_HOST: str = "localhost"
    CLICKHOUSE_PORT: int = 8123
    CLICKHOUSE_DB: str = "stock_tracker"
    CLICKHOUSE_PASSWORD: str = ""
    
    class Config:
        env_file = ".env"

settings = Settings()
#hehehe