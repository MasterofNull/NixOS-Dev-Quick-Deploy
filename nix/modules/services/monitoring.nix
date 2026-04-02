{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  mon = cfg.monitoring;
  mcp = cfg.mcpServers;
  ai = cfg.aiStack;
  tracing = mon.tracing;
  nodeTextfileDir = "/var/lib/node_exporter/textfile_collector";

  # ── Tempo configuration for distributed tracing ──────────────────────────────
  # Phase 21.1 — Lightweight trace storage with OTLP ingestion.
  tempoConfig = pkgs.writeText "tempo.yaml" ''
    stream_over_http_enabled: true
    server:
      http_listen_address: 127.0.0.1
      http_listen_port: ${toString tracing.tempoPort}
      grpc_listen_port: 9096

    distributor:
      receivers:
        otlp:
          protocols:
            grpc:
              endpoint: 127.0.0.1:${toString tracing.tempoOtlpGrpcPort}

    storage:
      trace:
        backend: local
        local:
          path: /var/lib/tempo/traces
        wal:
          path: /var/lib/tempo/wal

    compactor:
      compaction:
        block_retention: ${toString tracing.retentionHours}h

    metrics_generator:
      registry:
        external_labels:
          source: tempo
      storage:
        path: /var/lib/tempo/generator/wal
        remote_write:
          - url: http://127.0.0.1:${toString mon.prometheusPort}/api/v1/write
            send_exemplars: true
  '';
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
      # Phase 21.2 — LLM Token Throughput (actual llama.cpp metrics)
      {
        id = 7;
        type = "timeseries";
        title = "LLM Tokens/sec";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [
          { expr = "sum(rate(llamacpp_tokens_predicted_total[1m]))"; legendFormat = "generated"; refId = "A"; }
          { expr = "sum(rate(llamacpp_prompt_tokens_total[1m]))"; legendFormat = "prompt"; refId = "B"; }
        ];
        gridPos = { h = 8; w = 8; x = 0; y = 16; };
      }
      # Phase 21.2 — KV Cache Utilization
      {
        id = 8;
        type = "gauge";
        title = "KV Cache Usage (%)";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [{ expr = "100 * llamacpp_kv_cache_usage_ratio"; refId = "A"; }];
        gridPos = { h = 8; w = 4; x = 8; y = 16; };
        fieldConfig = {
          defaults = {
            min = 0;
            max = 100;
            thresholds = {
              mode = "absolute";
              steps = [
                { value = 0; color = "green"; }
                { value = 70; color = "yellow"; }
                { value = 90; color = "red"; }
              ];
            };
            unit = "percent";
          };
        };
      }
      # Phase 21.2 — Request Latency p95
      {
        id = 9;
        type = "timeseries";
        title = "Inference Latency p95 (s)";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [
          { expr = "histogram_quantile(0.95, sum by (le) (rate(llamacpp_request_processing_seconds_bucket[5m])))"; legendFormat = "p95"; refId = "A"; }
          { expr = "histogram_quantile(0.50, sum by (le) (rate(llamacpp_request_processing_seconds_bucket[5m])))"; legendFormat = "p50"; refId = "B"; }
        ];
        gridPos = { h = 8; w = 8; x = 12; y = 16; };
      }
      # Phase 21.2 — Active Requests / Slot Utilization
      {
        id = 10;
        type = "timeseries";
        title = "Active Requests";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [
          { expr = "llamacpp_requests_processing"; legendFormat = "processing"; refId = "A"; }
          { expr = "llamacpp_requests_pending"; legendFormat = "pending"; refId = "B"; }
        ];
        gridPos = { h = 8; w = 4; x = 20; y = 16; };
      }
      # Phase 21.1 — Trace throughput panel (OTEL collector metrics)
      {
        id = 11;
        type = "timeseries";
        title = "Traces/sec (OTEL)";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [
          { expr = "sum(rate(otelcol_receiver_accepted_spans[5m]))"; legendFormat = "accepted"; refId = "A"; }
          { expr = "sum(rate(otelcol_exporter_sent_spans[5m]))"; legendFormat = "exported"; refId = "B"; }
        ];
        gridPos = { h = 8; w = 12; x = 0; y = 24; };
      }
      # Phase 21.2 — Embedding Server Throughput
      {
        id = 12;
        type = "timeseries";
        title = "Embedding Tokens/sec";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [
          { expr = "sum(rate(llamacpp_prompt_tokens_total{job=\"llama-cpp-embed\"}[1m]))"; legendFormat = "tokens"; refId = "A"; }
        ];
        gridPos = { h = 8; w = 12; x = 12; y = 24; };
      }
      # Phase 21.3 — Embedding Cache Size
      {
        id = 13;
        type = "stat";
        title = "Cache Size (keys)";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [{ expr = "embedding_cache_size_keys"; refId = "A"; }];
        gridPos = { h = 4; w = 4; x = 0; y = 32; };
        fieldConfig = {
          defaults = {
            unit = "short";
            color = { mode = "thresholds"; };
            thresholds = {
              mode = "absolute";
              steps = [
                { value = 0; color = "blue"; }
              ];
            };
          };
        };
      }
      # Phase 21.3 — Cache Hit Rate
      {
        id = 14;
        type = "gauge";
        title = "Cache Hit Rate (%)";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [
          {
            expr = "100 * sum(rate(embedding_cache_hits_total[5m])) / clamp_min(sum(rate(embedding_cache_hits_total[5m])) + sum(rate(embedding_cache_misses_total[5m])), 1e-9)";
            refId = "A";
          }
        ];
        gridPos = { h = 4; w = 4; x = 4; y = 32; };
        fieldConfig = {
          defaults = {
            min = 0;
            max = 100;
            thresholds = {
              mode = "absolute";
              steps = [
                { value = 0; color = "red"; }
                { value = 50; color = "yellow"; }
                { value = 80; color = "green"; }
              ];
            };
            unit = "percent";
          };
        };
      }
      # Phase 21.3 — Cache Invalidations
      {
        id = 15;
        type = "timeseries";
        title = "Cache Invalidations/hr";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [
          { expr = "sum(increase(embedding_cache_invalidations_total[1h])) by (trigger)"; legendFormat = "{{trigger}}"; refId = "A"; }
        ];
        gridPos = { h = 4; w = 4; x = 8; y = 32; };
      }
      # Phase 5 — Model Reloads
      {
        id = 16;
        type = "stat";
        title = "Model Reloads (24h)";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [
          { expr = "sum(increase(model_reloads_total{status=\"success\"}[24h]))"; refId = "A"; }
        ];
        gridPos = { h = 4; w = 4; x = 12; y = 32; };
        fieldConfig = {
          defaults = {
            unit = "short";
            color = { mode = "thresholds"; };
            thresholds = {
              mode = "absolute";
              steps = [
                { value = 0; color = "green"; }
                { value = 5; color = "yellow"; }
                { value = 10; color = "orange"; }
              ];
            };
          };
        };
      }
      # Phase 5 — Model Reload Duration
      {
        id = 17;
        type = "gauge";
        title = "Last Reload Duration (s)";
        datasource = { type = "prometheus"; uid = "prometheus"; };
        targets = [
          { expr = "histogram_quantile(0.99, rate(model_reload_duration_seconds_bucket[1h]))"; refId = "A"; }
        ];
        gridPos = { h = 4; w = 4; x = 16; y = 32; };
        fieldConfig = {
          defaults = {
            min = 0;
            max = 120;
            unit = "s";
            thresholds = {
              mode = "absolute";
              steps = [
                { value = 0; color = "green"; }
                { value = 30; color = "yellow"; }
                { value = 60; color = "red"; }
              ];
            };
          };
        };
      }
    ];
  };
  amdgpuTextfileScript = pkgs.writeShellScript "emit-amdgpu-metrics" ''
    set -eu
    out_dir="${nodeTextfileDir}"
    out_file="$out_dir/amdgpu.prom"
    tmp_file="$(mktemp "$out_dir/amdgpu.prom.XXXXXX")"
    card_link="$(${pkgs.findutils}/bin/find /sys/class/drm -maxdepth 1 -type l -name 'card[0-9]*' 2>/dev/null | ${pkgs.coreutils}/bin/sort | ${pkgs.coreutils}/bin/head -n1 || true)"
    card_dev=""
    if [ -n "$card_link" ]; then
      card_dev="$(${pkgs.coreutils}/bin/readlink -f "$card_link/device" 2>/dev/null || true)"
    fi
    busy=0
    vram_used=0
    vram_total=0
    temp_c=0
    power_w=0
    if [ -n "$card_dev" ]; then
      busy="$(${pkgs.coreutils}/bin/cat "$card_dev/gpu_busy_percent" 2>/dev/null || echo 0)"
      vram_used="$(${pkgs.coreutils}/bin/cat "$card_dev/mem_info_vram_used" 2>/dev/null || echo 0)"
      vram_total="$(${pkgs.coreutils}/bin/cat "$card_dev/mem_info_vram_total" 2>/dev/null || echo 0)"
      hwmon_dir="$(${pkgs.findutils}/bin/find "$card_dev/hwmon" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | ${pkgs.coreutils}/bin/sort | ${pkgs.coreutils}/bin/head -n1 || true)"
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
    ${pkgs.coreutils}/bin/chmod 0644 "$tmp_file"
    ${pkgs.coreutils}/bin/mv "$tmp_file" "$out_file"
  '';
in
{
  config = lib.mkIf mon.enable {
    services.prometheus = {
      enable = true;
      port = mon.prometheusPort;
      # Security: bind to localhost unless explicitly exposing on LAN
      listenAddress = if mon.listenOnLan then "0.0.0.0" else "127.0.0.1";
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
        # Phase 21.2 — llama.cpp inference server metrics (token throughput, latency, KV cache)
        {
          job_name = "llama-cpp";
          metrics_path = "/metrics";
          static_configs = [{ targets = [ "127.0.0.1:${toString ai.llamaCpp.port}" ]; }];
        }
      ] ++ lib.optionals (cfg.roles.aiStack.enable && ai.embeddingServer.enable) [
        # Phase 21.2 — llama.cpp embedding server metrics
        {
          job_name = "llama-cpp-embed";
          metrics_path = "/metrics";
          static_configs = [{ targets = [ "127.0.0.1:${toString ai.embeddingServer.port}" ]; }];
        }
      ];
    };

    services.prometheus.exporters.node = {
      enable = true;
      port = mon.nodeExporterPort;
      # Security: bind to localhost unless explicitly exposing on LAN
      listenAddress = if mon.listenOnLan then "0.0.0.0" else "127.0.0.1";
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
          ] ++ lib.optionals tracing.enable [
            {
              name = "Tempo";
              uid = "tempo";
              type = "tempo";
              access = "proxy";
              url = "http://127.0.0.1:${toString tracing.tempoPort}";
              editable = false;
              jsonData = {
                tracesToLogsV2 = {
                  datasourceUid = "prometheus";
                };
                serviceMap = {
                  datasourceUid = "prometheus";
                };
                nodeGraph = {
                  enabled = true;
                };
                tracesToMetrics = {
                  datasourceUid = "prometheus";
                };
              };
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
    ] ++ lib.optionals tracing.enable [
      "d /var/lib/tempo 0750 tempo tempo -"
      "d /var/lib/tempo/traces 0750 tempo tempo -"
      "d /var/lib/tempo/wal 0750 tempo tempo -"
      "d /var/lib/tempo/generator 0750 tempo tempo -"
      "d /var/lib/tempo/generator/wal 0750 tempo tempo -"
    ];

    systemd.services.ai-amdgpu-metrics-exporter = {
      description = "Emit AMD GPU metrics for node_exporter textfile collector";
      wantedBy = [ "multi-user.target" ];
      after = [ "node-exporter.service" ];
      serviceConfig = {
        Type = "oneshot";
        User = "root";
        Nice = 15;
        IOSchedulingClass = "idle";
        TimeoutStartSec = "15s";
        ExecStart = "${amdgpuTextfileScript}";
      };
    };

    systemd.timers.ai-amdgpu-metrics-exporter = {
      description = "Periodic AMD GPU metrics collection timer";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "30s";
        OnUnitActiveSec = "${toString mon.amdgpuMetricsIntervalSeconds}s";
        AccuracySec = "30s";
        Unit = "ai-amdgpu-metrics-exporter.service";
      };
    };

    # ── Phase 21.1 — Grafana Tempo for distributed tracing ─────────────────────
    # Lightweight trace storage with OTLP gRPC ingestion.
    # Traces are stored locally with configurable retention.
    users.groups.tempo = lib.mkIf tracing.enable {};
    users.users.tempo = lib.mkIf tracing.enable {
      isSystemUser = true;
      group = "tempo";
      description = "Grafana Tempo trace storage";
      home = "/var/lib/tempo";
      createHome = true;
    };

    systemd.services.ai-tempo = lib.mkIf tracing.enable {
      description = "Grafana Tempo distributed tracing backend";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];
      serviceConfig = {
        Type = "simple";
        User = "tempo";
        Group = "tempo";
        Restart = "on-failure";
        RestartSec = "5s";
        StateDirectory = "tempo";
        ExecStart = "${pkgs.tempo}/bin/tempo -config.file=${tempoConfig}";
        # Hardening
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        ReadWritePaths = [ "/var/lib/tempo" ];
      };
    };

    networking.firewall.allowedTCPPorts = lib.mkIf mon.listenOnLan (
      [ mon.grafanaPort mon.prometheusPort mon.nodeExporterPort ]
      ++ lib.optionals tracing.enable [ tracing.tempoPort ]
    );
  };
}
