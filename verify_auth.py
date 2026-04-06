import requests

def verify_auth():
    url = "http://localhost:8000/auth/login"
    payload = {
        "email": "admin@behave.sec",
        "password": "password"
    }
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        if response.status_code == 200 and data.get("status") == "success":
            print("SUCCESS: Authentication system is working correctly.")
            print(f"User: {data['user']['full_name']} ({data['user']['email']})")
            print(f"Token: {data['access_token'][:10]}...")
        else:
            print(f"FAILURE: Authentication failed with status {response.status_code}.")
            print(f"Detail: {data.get('detail', 'No detail provided')}")
    except Exception as e:
        print(f"ERROR: Could not connect to the server: {e}")

if __name__ == "__main__":
    verify_auth()
