import urllib.request
import json
import urllib.error

url = "http://localhost:8000/api/v1/diagnose/stream"
data = {
    "description": "hi",
    "use_llm": True,
    "verbose": False
}
headers = {'Content-Type': 'application/json'}

req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')

try:
    with urllib.request.urlopen(req) as response:
        print(f"Status Code: {response.getcode()}")
        print(response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print(f"Status Code: {e.code}")
    print(e.read().decode('utf-8'))
except Exception as e:
    print(f"Request failed: {e}")
