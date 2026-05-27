import os
import urllib.request, json
key = open("/run/secrets/hybrid_coordinator_api_key").read().strip()
url = f"http://127.0.0.1:{os.environ.get('HYBRID_COORDINATOR_PORT', '8003')}/control/ai-coordinator/delegate"
payload = json.dumps({"task": "what is nixos"}).encode()
req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "X-API-Key": key}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print(resp.status, resp.read().decode())
except Exception as e:
    print(e)
