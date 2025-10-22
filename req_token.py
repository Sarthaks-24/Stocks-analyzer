import os
import requests
from dotenv import load_dotenv

# Configuration
NOTIFIER_ENDPOINT = "https://upstoxendpoint-faeuis-projects.vercel.app/api/notifier"
ENV_FILE = ".env"

def fetch_token_from_notifier():
    """Fetch access token from the Vercel notifier endpoint."""
    print("Fetching access token from notifier...")

    # No headers needed now
    try:
        response = requests.get(NOTIFIER_ENDPOINT, timeout=10)
        print(f"📡 Response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            if data.get('success') and data.get('is_valid'):
                access_token = data['access_token']
                expires_in_hours = data.get('expires_in_hours', 'unknown')
                stored_at = data.get('stored_at', 'unknown')

                print(f"Token retrieved successfully!")
                print(f"Expires in: {expires_in_hours} hours")
                print(f"Stored at: {stored_at}")

                return access_token
            else:
                print("Token is not valid or expired")
                return None

        elif response.status_code == 404:
            print("No token found in storage")
            print("Please run your token generation script first")
            return None

        elif response.status_code == 410:
            print("Token has expired")
            print("Please generate a new token")
            return None

        else:
            print(f"Unexpected response: {response.status_code}")
            print(f"Response: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error fetching token: {e}")
        return None

def update_env_file(access_token):
    """Update or add A_TOKEN in .env file, preserving other variables, and wrap value in double quotes."""
    print(f"Updating {ENV_FILE} file with new token...")

    lines = []
    found = False

    # Read existing lines if file exists
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r') as file:
            for line in file:
                if line.strip().startswith("A_TOKEN="):
                    lines.append(f'A_TOKEN="{access_token}"\n')
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f'A_TOKEN="{access_token}"\n')

    try:
        with open(ENV_FILE, 'w') as file:
            file.writelines(lines)
        print(f"{ENV_FILE} updated with new token")
        return True
    except Exception as e:
        print(f"Error writing {ENV_FILE}: {e}")
        return False

def verify_token_in_env():
    """Verify that the token was successfully updated in .env."""
    print("Verifying token in .env file...")
    
    try:
        # Reload environment variables
        load_dotenv(override=True)
        
        # Check if A_TOKEN exists and is not empty
        token = os.getenv('A_TOKEN')
        
        if token:
            print(f"Token verified in environment: {token[:20]}...")
            return True
        else:
            print("A_TOKEN not found in environment variables")
            return False
            
    except Exception as e:
        print(f"Error verifying token: {e}")
        return False

def main():
    """Main function to fetch token and update .env file."""
    print("Starting token update process...\n")
    
    # Step 1: Fetch token from notifier
    access_token = fetch_token_from_notifier()
    
    if not access_token:
        print("\nFailed to fetch valid token. Process aborted.")
        print("\nNext steps:")
        print("1. Make sure your token generation script has run")
        print("2. Check that the notifier endpoint is working")
        print("3. Verify the token hasn't expired")
        return False
    
    print(f"\nAccess token fetched: {access_token[:20]}...")
    
    # Step 2: Update .env file
    if not update_env_file(access_token):
        print("\nFailed to update .env file. Process aborted.")
        return False
    
    # Step 3: Verify the update
    if not verify_token_in_env():
        print("\nToken updated in file but verification failed.")
        print("You may need to restart your application.")
        return False
    
    print("\nSuccess! Token updated and verified in .env file")
    print("You can now run your market data fetching script.")
    
    return True

if __name__ == "__main__":
    success = main()
    
    if not success:
        print("\nProcess completed with errors")
        exit(1)
    else:
        print("\nProcess completed successfully")
        exit(0)