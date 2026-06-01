import requests

def test_login_and_generate_keys():
    session = requests.Session()
    # Assuming Administrator is active locally with password "Nigma@2004" or similar
    # Oh wait, the user's password for this instance is "Nigma@2004"
    login_res = session.post("http://127.0.0.1:8000/api/method/login", data={
        "usr": "Administrator",
        "pwd": "admin"
    })
    
    print("Login Response:", login_res.json())
    if login_res.status_code == 200:
        keys_res = session.post("http://127.0.0.1:8000/api/method/frappe.core.doctype.user.user.generate_keys", data={
            "user": "Administrator"
        })
        print("Generate Keys Response:", keys_res.json())
        
        user_res = session.get("http://127.0.0.1:8000/api/resource/User/Administrator")
        print("User Response:", user_res.json().get('data', {}).get('api_key'))
        
if __name__ == "__main__":
    test_login_and_generate_keys()
