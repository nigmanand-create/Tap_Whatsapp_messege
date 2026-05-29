import requests

url = "https://api.glific.com/"
r = requests.get(url)
print("Doc len:", len(r.text))
