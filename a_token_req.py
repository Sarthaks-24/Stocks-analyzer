import requests
from dotenv import load_dotenv
import os
load_dotenv()
def req_atoken():
    url = f"https://api.upstox.com/v3/login/auth/token/request/{os.getenv('C_ID')}"

    payload={
    "client_secret": os.getenv('C_SEC')
}
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, json=payload)

    print(response.text)

def get_access_token(env_path=".env"):
    """Reads ACCESS_TOKEN from a .env file."""
    try:
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("ACCESS_TOKEN="):
                    return line.strip().split("=", 1)[1]
    except Exception as e:
        print(f"Error reading .env: {e}")
    return None



req_atoken()