import frappe
from tap_buddy.services.glific_client import GlificClient

def check_glific_refresh():
    try:
        client = GlificClient()
        print("REST Base URL:", client.rest_base_url)
        print("Refresh Token Configured:", bool(client.refresh_token))
        
        # Test just by trying to hit the endpoint
        import requests
        url = f"{client.rest_base_url}/session/renew"
        headers = {
            "Authorization": client.refresh_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        resp = requests.post(url, headers=headers, json={}, timeout=10)
        print("Status Code:", resp.status_code)
        print("Response JSON:", resp.json() if resp.status_code in (200, 400, 401) else resp.text)
    except Exception as e:
        print("Exception:", str(e))
