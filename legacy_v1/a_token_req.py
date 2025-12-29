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



req_atoken()