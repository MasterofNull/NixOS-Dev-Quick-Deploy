{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  mon = cfg.monitoring;
  mcp = cfg.mcpServers;
  ai = cfg.aiStack;
  nodeTextfileDir = "/var/lib/node_exporter/textfile_collector";
  grafanaDashboard = builtins.toJSON {
    id = null;
    uid = "ai-stack-overview";
    title = "AI Inference Stack";
    tags = [ "ai" "llm" "nixos" ];
    timezone = "browser";
    schemaVersion = 39;
    version = 1;
    refresh = "10s";
    panels = [
      {
        id = 1;
        type = "timeseries";
        title = "GPU Utilization (%)";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [{ expr = "amdgpu_gpu_busy_percent"; refId = "A"; }];
        gridPos = { h = 8; w = 8; x = 0; y = 0; };
      }
      {
        id = 2;
        type = "timeseries";
        title = "VRAM Usage (%)";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [{ expr = "100 * amdgpu_vram_used_bytes / clamp_min(amdgpu_vram_total_bytes, 1)"; refId = "A"; }];
        gridPos = { h = 8; w = 8; x = 8; y = 0; };
      }
      {
        id = 3;
        type = "timeseries";
        title = "System RAM Usage (%)";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [{ expr = "100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))"; refId = "A"; }];
        gridPos = { h = 8; w = 8; x = 16; y = 0; };
      }
      {
        id = 4;
        type = "timeseries";
        title = "Embedding Cache Hit Rate (%)";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [
          {
            expr = "100 * sum(rate(embedding_cache_hits_total[5m])) / clamp_min(sum(rate(embedding_cache_hits_total[5m])) + sum(rate(embedding_cache_misses_total[5m])), 1e-9)";
            refId = "A";
          }
        ];
        gridPos = { h = 8; w = 8; x = 0; y = 8; };
      }
      {
        id = 5;
        type = "timeseries";
        title = "LLM Routing Split (req/s)";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [
          { expr = "sum(rate(hybrid_llm_backend_selections_total{backend=\"local\"}[5m]))"; legendFormat = "local"; refId = "A"; }
          { expr = "sum(rate(hybrid_llm_backend_selections_total{backend=\"remote\"}[5m]))"; legendFormat = "remote"; refId = "B"; }
        ];
        gridPos = { h = 8; w = 8; x = 8; y = 8; };
      }
      {
        id = 6;
        type = "timeseries";
        title = "p95 Backend Latency (s)";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [
          {
            expr = "histogram_quantile(0.95, sum by (le, backend) (rate(hybrid_llm_backend_latency_seconds_bucket[5m])))";
            legendFormat = "{{backend}}";
            refId = "A";
          }
        ];
        gridPos = { h = 8; w = 8; x = 16; y = 8; };
      }
      {
        id = 7;
        type = "timeseries";
        title = "LLM Tokens/sec (if exposed)";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [{ expr = "sum(rate(llamacpp_tokens_total[1m]))"; refId = "A"; }];
        gridPos = { h = 8; w = 24; x = 0; y = 16; };
      }
    ];
  };
  amdgpuTextfileScript = pkgs.writeShellScript "emit-amdgpu-metrics" ''
    set -eu
    out_dir="${nodeTextfileDir}"
    out_file="$out_dir/amdgpu.prom"
    tmp_file="$(mktemp "$out_dir/amdgpu.prom.XXXXXX")"
    card_dev="$(${pkgs.findutils}/bin/find /sys/class/drm -maxdepth 2 -type d -name device 2>/dev/null | ${pkgs.coreutils}/bin/head -n1 || true)"
    busy=0
    vram_used=0
    vram_total=0
    temp_c=0
    power_w=0
    if [ -n "$card_dev" ]; then
      busy="$(${pkgs.coreutils}/bin/cat "$card_dev/gpu_busy_percent" 2>/dev/null || echo 0)"
      vram_used="$(${pkgs.coreutils}/bin/cat "$card_dev/mem_info_vram_used" 2>/dev/null || echo 0)"
      vram_total="$(${pkgs.coreutils}/bin/cat "$card_dev/mem_info_vram_total" 2>/dev/null || echo 0)"
      hwmon_dir="$(${pkgs.findutils}/bin/find "$card_dev/hwmon" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | ${pkgs.coreutils}/bin/head -n1 || true)"
      if [ -n "$hwmon_dir" ]; then
        temp_mc="$(${pkgs.coreutils}/bin/cat "$hwmon_dir/temp1_input" 2>/dev/null || echo 0)"
        power_uw="$(${pkgs.coreutils}/bin/cat "$hwmon_dir/power1_average" 2>/dev/null || echo 0)"
        temp_c="$(${pkgs.gawk}/bin/awk "BEGIN { printf \"%.3f\", (''${temp_mc}+0)/1000.0 }")"
        power_w="$(${pkgs.gawk}/bin/awk "BEGIN { printf \"%.3f\", (''${power_uw}+0)/1000000.0 }")"
      fi
    fi
    cat > "$tmp_file" <<EOF
# HELP amdgpu_gpu_busy_percent AMD GPU busy percentage
# TYPE amdgpu_gpu_busy_percent gauge
amdgpu_gpu_busy_percent $busy
# HELP amdgpu_vram_used_bytes AMD GPU VRAM used bytes
# TYPE amdgpu_vram_used_bytes gauge
amdgpu_vram_used_bytes $vram_used
# HELP amdgpu_vram_total_bytes AMD GPU VRAM total bytes
# TYPE amdgpu_vram_total_bytes gauge
amdgpu_vram_total_bytes $vram_total
# HELP amdgpu_temperature_celsius AMD GPU edge temperature celsius
# TYPE amdgpu_temperature_celsius gauge
amdgpu_temperature_celsius $temp_c
# HELP amdgpu_power_watts AMD GPU power draw watts
# TYPE amdgpu_power_watts gauge
amdgpu_power_watts $power_w
EOF
    ${pkgs.coreutils}/bin/mv "$tmp_file" "$out_file"
  '';
in
{
  config = lib.mkIf mon.enable {
    services.prometheus = {
      enable = true;
      port = mon.prometheusPort;
      scrapeConfigs = [
        {
          job_name = "node";
          static_configs = [{ targets = [ "127.0.0.1:${toString mon.nodeExporterPort}" ]; }];
        }
      ] ++ lib.optionals (cfg.roles.aiStack.enable && mcp.enable && ai.backend == "llamacpp") [
        {
          job_name = "aidb";
          metrics_path = "/metrics";
          static_configs = [{ targets = [ "127.0.0.1:${toString mcp.aidbPort}" ]; }];
        }
        {
          job_name = "hybrid-coordinator";
          metrics_path = "/metrics";
          static_configs = [{ targets = [ "127.0.0.1:${toString mcp.hybridPort}" ]; }];
        }
      ];
    };

    services.prometheus.exporters.node = {
      enable = true;
      port = mon.nodeExporterPort;
      enabledCollectors = [
        "cpu"
        "diskstats"
        "filesystem"
        "hwmon"
        "loadavg"
        "meminfo"
        "netdev"
        "nvme"
        "processes"
        "systemd"
        "thermal_zone"
        "textfile"
      ];
      extraFlags = [ "--collector.textfile.directory=${nodeTextfileDir}" ];
    };

    services.grafana = {
      enable = true;
      settings = {
        server = {
          http_addr = if mon.listenOnLan then "0.0.0.0" else "127.0.0.1";
          http_port = mon.grafanaPort;
        };
        analytics = {
          reporting_enabled = false;
          check_for_updates = false;
        };
      };
      provision = {
        enable = true;
        datasources.settings = {
          apiVersion = 1;
          datasources = [
            {
              name = "Prometheus";
              uid = "prometheus";
              type = "prometheus";
              access = "proxy";
              url = "http://127.0.0.1:${toString mon.prometheusPort}";
              isDefault = true;
              editable = false;
            }
          ];
        };
        dashboards.settings = {
          apiVersion = 1;
          providers = [
            {
              name = "AI Stack Dashboards";
              orgId = 1;
              folder = "AI Stack";
              type = "file";
              disableDeletion = false;
              updateIntervalSeconds = 30;
              options.path = "/etc/grafana-dashboards";
            }
          ];
        };
      };
    };

    environment.etc."grafana-dashboards/ai-stack-overview.json".text = grafanaDashboard;

    systemd.tmpfiles.rules = [
      "d ${nodeTextfileDir} 0755 node-exporter node-exporter -"
    ];

    systemd.services.ai-amdgpu-metrics-exporter = {
      description = "Emit AMD GPU metrics for node_exporter textfile collector";
      wantedBy = [ "multi-user.target" ];
      after = [ "node-exporter.service" ];
      serviceConfig = {
        Type = "oneshot";
        User = "root";
        ExecStart = "${amdgpuTextfileScript}";
      };
    };

    systemd.timers.ai-amdgpu-metrics-exporter = {
      description = "Periodic AMD GPU metrics collection timer";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "30s";
        OnUnitActiveSec = "15s";
        Unit = "ai-amdgpu-metrics-exporter.service";
      };
    };

    networking.firewall.allowedTCPPorts = lib.mkIf mon.listenOnLan [
      mon.grafanaPort
      mon.prometheusPort
      mon.nodeExporterPort
    ];
  };
}
