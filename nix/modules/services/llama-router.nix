{
  config,
  lib,
  pkgs,
  ...
}:
with lib; let
  cfg = config.mySystem.aiStack.llamaRouter;
  llamaCppCfg = config.mySystem.aiStack.llamaCpp;
in {
  options.mySystem.aiStack.llamaRouter = {
    enable = mkEnableOption "llama.cpp router service";
    port = mkOption {
      type = types.port;
      default = 8088; # A new port for the router
      description = "Port for the Llama Router service.";
    };
    llamaCppUrl = mkOption {
      type = types.str;
      default = "http://127.0.0.1:${toString llamaCppCfg.port}";
      description = "URL of the upstream llama.cpp instance.";
    };
    queueSize = mkOption {
      type = types.int;
      default = 10;
      description = "Maximum size of the request queue.";
    };
    timeoutSeconds = mkOption {
      type = types.int;
      default = 10; # Default timeout for forwarding requests
      description = "Timeout in seconds for forwarding requests to llama.cpp.";
    };
  };

  config = mkIf cfg.enable {
    systemd.services.llama-router = {
      description = "Llama.cpp Router Service";
      wantedBy = ["multi-user.target"];
      after = ["network.target" "llama-cpp.service"]; # Depends on llama-cpp
      serviceConfig = {
        Type = "simple";
        User = "llama"; # Run as the llama user
        Group = "llama";
        Restart = "on-failure";
        RestartSec = "5s";
        ExecStart = "${pkgs.python3.withPackages (ps: with ps; [aiohttp httpx])}/bin/python3 ${pkgs.writeText "llama-router-script" ''
          import asyncio
          import aiohttp
          import json
          import sys
          from collections import deque

          LLAMA_CPP_URL = "${cfg.llamaCppUrl}"
          ROUTER_PORT = ${toString cfg.port}
          QUEUE_SIZE = ${toString cfg.queueSize}
          TIMEOUT_SECONDS = ${toString cfg.timeoutSeconds}

          request_queue = deque(maxlen=QUEUE_SIZE)
          processing_lock = asyncio.Lock()
          THERMAL_PATH = "/sys/class/thermal/thermal_zone0/temp"

          def get_temperature():
              try:
                  with open(THERMAL_PATH, "r") as f:
                      return int(f.read().strip()) / 1000.0
              except Exception:
                  return 50.0 # Safe default

          async def forward_request(session, request_json):
              temp = get_temperature()
              if temp > 75.0:
                  print(f"THERMAL CRITICAL: {temp}C. Throttling request.")
                  await asyncio.sleep(2.0) # Artificial delay to allow cooling

              try:
                  async with session.post(f"{LLAMA_CPP_URL}/v1/chat/completions",
                                          json=request_json,
                                          timeout=TIMEOUT_SECONDS) as response:
                      response.raise_for_status()
                      return await response.json()
              except asyncio.TimeoutError:
                  return {"error": "Upstream LLM timed out"}
              except aiohttp.ClientError as e:
                  return {"error": f"Upstream LLM connection error: {e}"}
              except Exception as e:
                  return {"error": f"An unexpected error occurred: {e}"}

          async def handle_request(request):
              # This is a placeholder for the actual request handling logic.
              # In a real scenario, this would involve parsing the incoming HTTP request,
              # extracting the payload, and deciding whether to queue or process.
              # For this service, we're assuming a simple JSON-RPC style input from a client.
              return await forward_request(aiohttp.ClientSession(), request)

          async def process_queue():
              while True:
                  if request_queue and not processing_lock.locked():
                      async with processing_lock:
                          request_json = request_queue.popleft()
                          print(f"Processing queued request: {request_json.get('id')}")
                          result = await handle_request(request_json)
                          # Send result back to original client (needs more advanced IPC for real HTTP)
                          # For now, just log or send to a designated callback
                          print(f"Result for {request_json.get('id')}: {json.dumps(result)}")
                  await asyncio.sleep(0.1) # Small delay to prevent busy-waiting

          async def start_router():
              print(f"Llama Router starting on port {ROUTER_PORT}")
              # This example assumes a simple stdin/stdout interface for demonstration.
              # A real HTTP server would be implemented here using aiohttp.web
              # For now, we simulate processing via direct calls or IPC.
              asyncio.create_task(process_queue())

              # Simple stdin listener for demo purposes
              while True:
                  line = await asyncio.to_thread(sys.stdin.readline)
                  if not line:
                      break
                  try:
                      request_json = json.loads(line.strip())
                      if len(request_queue) < QUEUE_SIZE:
                          request_queue.append(request_json)
                          print(f"Request {request_json.get('id')} queued. Queue size: {len(request_queue)}")
                          # In a real HTTP server, we would respond with 202 Accepted.
                      else:
                          print(f"Request {request_json.get('id')} rejected: queue full.")
                          # In a real HTTP server, respond with 503 Service Unavailable.
                  except json.JSONDecodeError:
                      print("Received malformed JSON.")
                  except Exception as e:
                      print(f"Error handling request: {e}")
              print("Llama Router shutting down.")

          if __name__ == "__main__":
              asyncio.run(start_router())
        ''}";
        # Security hardening
        PrivateTmp = true;
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        PrivateDevices = false;
        IPAddressAllow = ["127.0.0.1/8" "::1/128"]; # Only allow local access
      };

      networking.firewall.allowedTCPPorts = lib.mkIf cfg.enable [cfg.port];
    };
  };
}
