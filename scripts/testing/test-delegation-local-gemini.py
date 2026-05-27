import os
import urllib.request, json
key = open("/run/secrets/hybrid_coordinator_api_key").read().strip()
url = f"http://127.0.0.1:{os.environ.get('HYBRID_COORDINATOR_PORT', '8003')}/control/ai-coordinator/delegate"

# Test local-agent profile
payload_local = json.dumps({"task": "list files in current directory", "profile": "local-agent"}).encode()
# Test remote-gemini profile
payload_gemini = json.dumps({"task": "what is nixos", "profile": "remote-gemini"}).encode()

def test_delegation(payload, profile):
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "X-API-Key": key}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"Profile: {profile}, Status: {resp.status}, Response: {resp.read().decode()[:100]}")
    except Exception as e:
        print(f"Profile: {profile}, Error: {e}")

print("Testing delegation lanes...")
test_delegation(payload_local, "local-agent")
test_delegation(payload_gemini, "remote-gemini")
