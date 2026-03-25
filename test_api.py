import urllib.request
import json

payload = json.dumps({"phone_number": "+919999999999"}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/chat-sessions/list/",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    resp = urllib.request.urlopen(req, timeout=25)
    print("Status:", resp.status)
    print("Response:", resp.read().decode())
except Exception as e:
    print(f"Error: {e}")
