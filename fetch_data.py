# Import necessary modules
import os, asyncio, json, ssl, websockets, requests
from datetime import datetime
from google.protobuf.json_format import MessageToDict
from dotenv import load_dotenv

load_dotenv()

import MarketDataFeedV3_pb2 as pb


def get_market_data_feed_authorize_v3():
    """Get authorization for market data feed."""
    access_token = os.getenv('A_TOKEN')
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    url = 'https://api.upstox.com/v3/feed/market-data-feed/authorize'
    api_response = requests.get(url=url, headers=headers)
    print(f"DEBUG: Authorization response status: {api_response.status_code}")

    return api_response.json()


def decode_protobuf(buffer):
    """Decode protobuf message."""
    feed_response = pb.FeedResponse()
    feed_response.ParseFromString(buffer)
    return feed_response


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
            with open('resources/instruments.txt','r') as f:
                instruments = f.read().split('\n')
            # Data to be sent over the WebSocket
            data = {
                "guid": "someguid",
                "method": "sub",
                "data": {
                    "mode": "full",
                    "instrumentKeys": instruments
                }
            }

            # Convert data to binary and send over WebSocket
            binary_data = json.dumps(data).encode('utf-8')
            await websocket.send(binary_data)
            print("DEBUG: Subscription sent")

            # Continuously receive and decode data from WebSocket
            while True:
                try:
                    message = await websocket.recv()
                    decoded_data = decode_protobuf(message)
                    data_dict = MessageToDict(decoded_data)

                    feeds = data_dict.get("feeds", {})
                    today = datetime.today().date()

                    for instrument_key, feed_data in feeds.items():
                        # Make filename safe by replacing | with _
                        safe_name = instrument_key.replace("|", "_")
                        dir_path = f"data/{safe_name}"
                        filename = f"{dir_path}/{today}.json"

                        # Ensure the directory exists
                        os.makedirs(dir_path, exist_ok=True)

                        with open(filename, 'a+', encoding='utf-8') as f:
                            json.dump(feed_data, f, ensure_ascii=False)
                            f.write('\n')

                    print(json.dumps(data_dict, indent=2))

                except websockets.exceptions.ConnectionClosed:
                    print("DEBUG: WebSocket connection closed")
                    break
                except Exception as e:
                    print(f"ERROR: Error receiving data: {e}")
                    break

    except Exception as e:
        print(f"ERROR: WebSocket connection failed: {e}")


if __name__ == "__main__":
    # Execute the function to fetch market data
    asyncio.run(fetch_market_data())