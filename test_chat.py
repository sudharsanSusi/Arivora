import requests
import json

api_key = "AIzaSyCs9AOVmF2wr4UMCfder-zXjmkNWb6bpJM"
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"

payload = {
    "contents": [{"role": "user", "parts": [{"text": "Hello"}]}],
    "systemInstruction": {"parts": [{"text": "System text"}]},
    "generationConfig": {"temperature": 0.5, "maxOutputTokens": 4096}
}

res = requests.post(url, json=payload)
print(res.status_code)
print(res.text)
