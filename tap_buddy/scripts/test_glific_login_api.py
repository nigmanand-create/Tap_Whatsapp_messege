import requests
import json

def test_glific_login():
    phone = "918595701049"  # this is what normalize_phone returns
    password = "Nigma@2004"
    url = "https://api.tap.glific.com/api/v1/session"
    
    print(f"Sending request to {url}")
    print(f"Payload: {json.dumps({'user': {'phone': phone, 'password': password}})}")
    
    res = requests.post(
        url,
        json={"user": {"phone": phone, "password": password}},
        headers={"Content-Type": "application/json"},
        timeout=15
    )
    
    print(f"Status Code: {res.status_code}")
    print(f"Response: {res.text}")

if __name__ == "__main__":
    test_glific_login()
