import urllib.request
import json

payload = {
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"}
    ],
    "max_tokens": 10,
    "stream": True,
    "temperature": 0.7
}
url = "http://localhost:8080/v1/chat/completions"
req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST"
)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        for line in resp:
            print(line.decode("utf-8"))
except Exception as e:
    print("Error:", e)
