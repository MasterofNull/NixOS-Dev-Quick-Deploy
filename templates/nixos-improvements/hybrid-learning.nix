{ config, lib, pkgs, ... }:

# ============================================================================
# Hybrid Local-Remote AI Learning System
# ============================================================================
# NixOS module for persistent, declarative hybrid learning configuration
# Automatically integrated with nixos-quick-deploy
# ============================================================================

with lib;

let
  cfg = config.services.hybridLearning;

  # Python environment with all dependencies
  pythonEnv = pkgs.python3.withPackages (ps: with ps; [
    httpx
    pydantic
    python-dotenv
    # Note: mcp and qdrant-client may need to be added to nixpkgs or use buildPythonPackage
  ]);

  # Hybrid coordinator service script
  hybridCoordinatorScript = pkgs.writeShellScriptBin "hybrid-coordinator" ''
    #!/usr/bin/env bash
    set -euo pipefail

    export QDRANT_URL="${cfg.qdrant.url}"
    export LEMONADE_BASE_URL="${cfg.lemonade.baseUrl}"
    export LEMONADE_CODER_URL="${cfg.lemonade.coderUrl}"
    export LEMONADE_DEEPSEEK_URL="${cfg.lemonade.deepseekUrl}"
    export LOCAL_CONFIDENCE_THRESHOLD="${toString cfg.learning.localConfidenceThreshold}"
    export HIGH_VALUE_THRESHOLD="${toString cfg.learning.highValueThreshold}"
    export PATTERN_EXTRACTION_ENABLED="${if cfg.learning.patternExtractionEnabled then "true" else "false"}"
    export AUTO_FINETUNE_ENABLED="${if cfg.learning.autoFinetuneEnabled then "true" else "false"}"
    export FINETUNE_DATA_PATH="${cfg.paths.finetuneData}"

    exec ${pythonEnv}/bin/python ${cfg.paths.coordinatorScript}
  '';

  # Data sync service script
  dataSyncScript = pkgs.writeShellScriptBin "hybrid-learning-sync" ''
    #!/usr/bin/env bash
    set -euo pipefail

    # Sync with federation nodes
    ${pythonEnv}/bin/python ${cfg.paths.syncScript} \
      --nodes "${concatStringsSep "," cfg.federation.nodes}" \
      --mode "${cfg.federation.mode}" \
      --sync-interval "${toString cfg.federation.syncInterval}"
  '';

in {
  # ============================================================================
  # Options
  # ============================================================================

  options.services.hybridLearning = {
    enable = mkEnableOption "Hybrid Local-Remote AI Learning System";

    paths = {
      coordinatorScript = mkOption {
        type = types.path;
        default = /var/lib/hybrid-learning/coordinator/server.py;
        description = "Path to hybrid coordinator MCP server script";
      };

      syncScript = mkOption {
        type = types.path;
        default = /var/lib/hybrid-learning/sync/federation-sync.py;
        description = "Path to federation sync script";
      };

      dataDir = mkOption {
        type = types.path;
        default = "/var/lib/hybrid-learning";
        description = "Base directory for hybrid learning data";
      };

      modelsDir = mkOption {
        type = types.path;
        default = "/var/lib/hybrid-learning/models";
        description = "Directory for GGUF models and fine-tuned models";
      };

      finetuneData = mkOption {
        type = types.path;
        default = "/var/lib/hybrid-learning/fine-tuning/dataset.jsonl";
        description = "Path to fine-tuning dataset";
      };

      exportDir = mkOption {
        type = types.path;
        default = "/var/lib/hybrid-learning/exports";
        description = "Directory for data exports (for portability)";
      };
    };

    qdrant = {
      url = mkOption {
        type = types.str;
        default = "http://localhost:6333";
        description = "Qdrant vector database URL";
      };

      apiKey = mkOption {
        type = types.nullOr types.str;
        default = null;
        description = "Qdrant API key (optional)";
      };
    };

    lemonade = {
      baseUrl = mkOption {
        type = types.str;
        default = "http://localhost:8080";
        description = "Lemonade general purpose inference URL";
      };

      coderUrl = mkOption {
        type = types.str;
        default = "http://localhost:8001/api/v1";
        description = "Lemonade coder inference URL";
      };

      deepseekUrl = mkOption {
        type = types.str;
        default = "http://localhost:8003/api/v1";
        description = "Lemonade deepseek inference URL";
      };
    };

    learning = {
      localConfidenceThreshold = mkOption {
        type = types.float;
        default = 0.7;
        description = "Threshold for routing to local LLM (0.0-1.0)";
      };

      highValueThreshold = mkOption {
        type = types.float;
        default = 0.7;
        description = "Threshold for high-value interaction extraction (0.0-1.0)";
      };

      patternExtractionEnabled = mkOption {
        type = types.bool;
        default = true;
        description = "Enable automatic pattern extraction from interactions";
      };

      autoFinetuneEnabled = mkOption {
        type = types.bool;
        default = false;
        description = "Enable automatic fine-tuning (requires significant resources)";
      };

      finetuneIntervalDays = mkOption {
        type = types.int;
        default = 30;
        description = "Days between automatic fine-tuning runs";
      };
    };

    federation = {
      enable = mkEnableOption "Multi-node federation and data synchronization";

      nodeId = mkOption {
        type = types.str;
        default = config.networking.hostName;
        description = "Unique identifier for this node";
      };

      mode = mkOption {
        type = types.enum [ "peer" "hub" "spoke" ];
        default = "peer";
        description = ''
          Federation mode:
          - peer: Equal peer-to-peer synchronization
          - hub: Central aggregation node
          - spoke: Edge node that syncs with hub
        '';
      };

      nodes = mkOption {
        type = types.listOf types.str;
        default = [];
        description = "List of federation node URLs (e.g., http://node1:8092)";
        example = [ "http://node1.example.com:8092" "http://node2.example.com:8092" ];
      };

      syncInterval = mkOption {
        type = types.int;
        default = 3600;
        description = "Seconds between automatic synchronization (default: 1 hour)";
      };

      conflictResolution = mkOption {
        type = types.enum [ "latest" "highest-value" "merge" "manual" ];
        default = "highest-value";
        description = ''
          Conflict resolution strategy:
          - latest: Most recent update wins
          - highest-value: Highest value score wins
          - merge: Combine data intelligently
          - manual: Require manual resolution
        '';
      };
    };

    monitoring = {
      enable = mkEnableOption "Prometheus metrics export";

      port = mkOption {
        type = types.port;
        default = 9200;
        description = "Port for Prometheus metrics";
      };
    };

    backup = {
      enable = mkEnableOption "Automatic backup of learning data";

      schedule = mkOption {
        type = types.str;
        default = "daily";
        description = "Backup schedule (systemd timer format)";
      };

      destination = mkOption {
        type = types.path;
        default = "/var/backups/hybrid-learning";
        description = "Backup destination directory";
      };

      retention = mkOption {
        type = types.int;
        default = 30;
        description = "Days to retain backups";
      };
    };
  };

  # ============================================================================
  # Implementation
  # ============================================================================

  config = mkIf cfg.enable {

    # Create persistent directories
    systemd.tmpfiles.rules = [
      "d ${cfg.paths.dataDir} 0755 root root -"
      "d ${cfg.paths.modelsDir} 0755 root root -"
      "d ${cfg.paths.exportDir} 0755 root root -"
      "d ${dirOf cfg.paths.finetuneData} 0755 root root -"
      "d ${cfg.backup.destination} 0755 root root -"
    ];

    # Hybrid Coordinator Service
    systemd.services.hybrid-coordinator = {
      description = "Hybrid AI Learning Coordinator MCP Server";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" "qdrant.service" ];
      wants = [ "qdrant.service" ];

      serviceConfig = {
        Type = "simple";
        ExecStart = "${hybridCoordinatorScript}/bin/hybrid-coordinator";
        Restart = "always";
        RestartSec = 10;

        # Security hardening
        DynamicUser = true;
        StateDirectory = "hybrid-learning";
        CacheDirectory = "hybrid-learning";
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        NoNewPrivileges = true;

        # Resource limits
        MemoryMax = "2G";
        CPUQuota = "50%";
      };

      environment = {
        QDRANT_URL = cfg.qdrant.url;
        LEMONADE_BASE_URL = cfg.lemonade.baseUrl;
        PYTHONUNBUFFERED = "1";
      };
    };

    # Federation Sync Service (if enabled)
    systemd.services.hybrid-learning-sync = mkIf cfg.federation.enable {
      description = "Hybrid Learning Federation Sync";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" "hybrid-coordinator.service" ];
      wants = [ "hybrid-coordinator.service" ];

      serviceConfig = {
        Type = "simple";
        ExecStart = "${dataSyncScript}/bin/hybrid-learning-sync";
        Restart = "always";
        RestartSec = 60;

        # Security
        DynamicUser = true;
        StateDirectory = "hybrid-learning";
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
      };
    };

    # Automatic Backup Service
    systemd.services.hybrid-learning-backup = mkIf cfg.backup.enable {
      description = "Backup Hybrid Learning Data";
      serviceConfig = {
        Type = "oneshot";
        ExecStart = pkgs.writeShellScript "hybrid-learning-backup" ''
          #!/usr/bin/env bash
          set -euo pipefail

          BACKUP_DIR="${cfg.backup.destination}/$(date +%Y%m%d-%H%M%S)"
          mkdir -p "$BACKUP_DIR"

          # Backup Qdrant data
          echo "Backing up Qdrant data..."
          ${pkgs.curl}/bin/curl -X POST "${cfg.qdrant.url}/collections/backup" \
            -o "$BACKUP_DIR/qdrant-backup.tar.gz" || true

          # Backup fine-tuning datasets
          echo "Backing up fine-tuning data..."
          cp -r ${cfg.paths.dataDir}/fine-tuning "$BACKUP_DIR/" || true

          # Backup models
          echo "Backing up fine-tuned models..."
          cp -r ${cfg.paths.modelsDir}/*.gguf "$BACKUP_DIR/" 2>/dev/null || true

          # Cleanup old backups
          echo "Cleaning up old backups..."
          find ${cfg.backup.destination} -type d -mtime +${toString cfg.backup.retention} -exec rm -rf {} + || true

          echo "Backup complete: $BACKUP_DIR"
        '';
      };
    };

    # Backup Timer
    systemd.timers.hybrid-learning-backup = mkIf cfg.backup.enable {
      description = "Hybrid Learning Backup Timer";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = cfg.backup.schedule;
        Persistent = true;
      };
    };

    # Auto Fine-tuning Service (if enabled)
    systemd.services.hybrid-learning-finetune = mkIf cfg.learning.autoFinetuneEnabled {
      description = "Automatic Fine-tuning of Local LLMs";
      serviceConfig = {
        Type = "oneshot";
        ExecStart = pkgs.writeShellScript "hybrid-learning-finetune" ''
          #!/usr/bin/env bash
          set -euo pipefail

          echo "Starting automatic fine-tuning..."

          # Generate dataset
          ${pythonEnv}/bin/python -c "
          import asyncio
          from hybrid_coordinator import generate_fine_tuning_dataset
          asyncio.run(generate_fine_tuning_dataset())
          "

          # Fine-tune model (placeholder - actual implementation depends on setup)
          echo "Fine-tuning would run here (requires GPU and significant resources)"
          # unsloth-finetune or llama-cpp fine-tune command here

          echo "Fine-tuning complete"
        '';
      };
    };

    # Auto Fine-tuning Timer
    systemd.timers.hybrid-learning-finetune = mkIf cfg.learning.autoFinetuneEnabled {
      description = "Automatic Fine-tuning Timer";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*-*-01,15 02:00:00";  # 1st and 15th of month at 2 AM
        Persistent = true;
      };
    };

    # Monitoring Exporter (if enabled)
    systemd.services.hybrid-learning-exporter = mkIf cfg.monitoring.enable {
      description = "Hybrid Learning Prometheus Exporter";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" "hybrid-coordinator.service" ];

      serviceConfig = {
        Type = "simple";
        ExecStart = pkgs.writeShellScript "hybrid-learning-exporter" ''
          #!/usr/bin/env bash
          ${pythonEnv}/bin/python -m prometheus_client.exposition ${toString cfg.monitoring.port}
        '';
        Restart = "always";
        DynamicUser = true;
      };
    };

    # Open firewall for MCP server and federation
    networking.firewall.allowedTCPPorts = mkIf cfg.enable [
      # MCP server port (adjust as needed)
      # 8092  # Federation sync port
    ] ++ optional cfg.monitoring.enable cfg.monitoring.port;

    # Environment variables for user sessions
    environment.sessionVariables = {
      HYBRID_LEARNING_ENABLED = "true";
      QDRANT_URL = cfg.qdrant.url;
      LEMONADE_BASE_URL = cfg.lemonade.baseUrl;
    };

    # Add management scripts to system PATH
    environment.systemPackages = with pkgs; [
      hybridCoordinatorScript
      (mkIf cfg.federation.enable dataSyncScript)
    ];

    # Documentation
    environment.etc."nixos/HYBRID-LEARNING.txt".text = ''
      ========================================
      Hybrid Local-Remote AI Learning System
      ========================================

      This NixOS system has hybrid learning enabled!

      Services:
        • Hybrid Coordinator: systemctl status hybrid-coordinator
        • Federation Sync:     systemctl status hybrid-learning-sync ${optionalString (!cfg.federation.enable) "(disabled)"}
        • Auto Backup:         systemctl status hybrid-learning-backup ${optionalString (!cfg.backup.enable) "(disabled)"}
        • Auto Fine-tune:      systemctl status hybrid-learning-finetune ${optionalString (!cfg.learning.autoFinetuneEnabled) "(disabled)"}

      Data Locations:
        • Base Directory:      ${cfg.paths.dataDir}
        • Models:              ${cfg.paths.modelsDir}
        • Fine-tuning Data:    ${cfg.paths.finetuneData}
        • Exports:             ${cfg.paths.exportDir}
        • Backups:             ${cfg.backup.destination}

      Configuration:
        • Node ID:             ${cfg.federation.nodeId}
        • Federation Mode:     ${cfg.federation.mode}
        • Connected Nodes:     ${toString (length cfg.federation.nodes)}

      Thresholds:
        • Local Confidence:    ${toString cfg.learning.localConfidenceThreshold}
        • High Value:          ${toString cfg.learning.highValueThreshold}

      Monitoring:
        • Qdrant:              ${cfg.qdrant.url}
        • Lemonade General:    ${cfg.lemonade.baseUrl}
        • Metrics:             http://localhost:${toString cfg.monitoring.port}/metrics ${optionalString (!cfg.monitoring.enable) "(disabled)"}

      Management:
        • View logs:           journalctl -u hybrid-coordinator -f
        • Manual backup:       systemctl start hybrid-learning-backup
        • Trigger sync:        systemctl start hybrid-learning-sync
        • Force fine-tune:     systemctl start hybrid-learning-finetune

      Documentation:
        • Architecture:        /etc/nixos/docs/HYBRID-LEARNING-ARCHITECTURE.md
        • User Guide:          /etc/nixos/docs/HYBRID-AI-SYSTEM-GUIDE.md
    '';
  };
}
