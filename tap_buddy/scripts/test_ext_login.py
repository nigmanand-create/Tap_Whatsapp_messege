import requests

def test():
    session = requests.Session()
    res = session.post("https://lms.evalix.xyz/api/method/login", data={
        "usr": "manu.aguest@theapprenticeproject.org",
        "pwd": "Tap@123"
    }, verify=False)
    print(res.status_code)
    print(res.text)

if __name__ == "__main__":
    test()
