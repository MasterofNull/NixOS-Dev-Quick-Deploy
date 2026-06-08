import httpx
import json
import sys

def test_discipline():
    url = "http://127.0.0.1:8003/control/ai-coordinator/delegate"
    payload = {
        "task": "Return exactly PLANNING_SMOKE_OK",
        "profile": "local-tool-calling",
        "max_tokens": 32,
        "temperature": 0.0
    }

    print(f"Calling {url} with task: {payload['task']}")
    try:
        r = httpx.post(url, json=payload, timeout=60.0)
        print(f"Status Code: {r.status_code}")
        if r.status_code != 200:
            print(f"Error: {r.text}")
            sys.exit(1)
        
        data = r.json()
        content = data["choices"][0]["message"]["content"].strip()
        print(f"Received Content: '{content}'")
        
        # The goal is EXACT output. No meta-reasoning.
        if content == "PLANNING_SMOKE_OK":
            print("PASS: Exact output achieved.")
        else:
            print(f"FAIL: Content mismatch. Expected 'PLANNING_SMOKE_OK', got '{content}'")
            sys.exit(1)
            
    except Exception as e:
        print(f"Exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_discipline()
