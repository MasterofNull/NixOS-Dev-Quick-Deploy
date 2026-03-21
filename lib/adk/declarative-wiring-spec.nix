# lib/adk/declarative-wiring-spec.nix
#
# Purpose: Declarative-first wiring requirements for ADK-aligned integrations
#
# Status: production
# Owner: ai-harness
# Last Updated: 2026-03-20
#
# Features:
# - Nix module template for ADK integrations
# - Option schema for ADK agent configuration
# - Environment injection patterns (no hardcoded ports/URLs)
# - Service dependency declarations
# - Tool adapter registration
# - Observability hook configuration
# - A2A endpoint configuration
# - Example integration modules

{ config, lib, pkgs, ... }:

with lib;

let
  cfg = config.mySystem.aiStack.adk;

  # ADK Integration Module Type
  adkIntegrationType = types.submodule {
    options = {
      name = mkOption {
        type = types.str;
        description = "Unique name for this ADK integration";
        example = "google-adk-agent";
      };

      enable = mkOption {
        type = types.bool;
        default = false;
        description = "Enable this ADK integration";
      };

      package = mkOption {
        type = types.nullOr types.package;
        default = null;
        description = "Package providing the ADK integration";
      };

      # Environment Configuration (No Hardcoded Values)
      environment = {
        baseUrl = mkOption {
          type = types.str;
          description = "Base URL for the ADK service (from ports module)";
          example = "http://127.0.0.1:\${toString config.mySystem.ports.adkAgent}";
        };

        apiKeyFile = mkOption {
          type = types.nullOr types.path;
          default = null;
          description = "Path to API key file (never inline secrets)";
        };

        configFile = mkOption {
          type = types.nullOr types.path;
          default = null;
          description = "Path to JSON configuration file";
        };

        extraEnv = mkOption {
          type = types.attrsOf types.str;
          default = {};
          description = "Additional environment variables";
          example = {
            ADK_LOG_LEVEL = "info";
            ADK_TIMEOUT = "30";
          };
        };
      };

      # Service Dependencies
      dependencies = {
        services = mkOption {
          type = types.listOf types.str;
          default = [];
          description = "SystemD services this integration depends on";
          example = [ "ai-hybrid-coordinator.service" "postgresql.service" ];
        };

        ports = mkOption {
          type = types.listOf types.str;
          default = [];
          description = "Port configuration dependencies";
          example = [ "adkAgent" "hybridCoordinator" ];
        };
      };

      # A2A (Agent-to-Agent) Protocol Configuration
      a2a = {
        enable = mkOption {
          type = types.bool;
          default = true;
          description = "Enable A2A protocol support";
        };

        protocolVersion = mkOption {
          type = types.str;
          default = "1.0";
          description = "A2A protocol version";
        };

        endpoints = {
          discovery = mkOption {
            type = types.str;
            description = "Agent discovery endpoint";
            example = "/a2a/discover";
          };

          task = mkOption {
            type = types.str;
            description = "Task submission endpoint";
            example = "/a2a/task";
          };

          event = mkOption {
            type = types.str;
            description = "Event streaming endpoint";
            example = "/a2a/events";
          };

          result = mkOption {
            type = types.str;
            description = "Result retrieval endpoint";
            example = "/a2a/result";
          };
        };

        agentCard = {
          name = mkOption {
            type = types.str;
            description = "Agent display name";
          };

          version = mkOption {
            type = types.str;
            description = "Agent version";
          };

          capabilities = mkOption {
            type = types.listOf types.str;
            default = [];
            description = "Agent capabilities";
            example = [ "task_execution" "event_streaming" "tool_calling" ];
          };

          protocols = mkOption {
            type = types.listOf types.str;
            default = [ "a2a" "openai" ];
            description = "Supported protocols";
          };
        };
      };

      # Tool Adapter Registration
      tools = {
        enable = mkOption {
          type = types.bool;
          default = true;
          description = "Enable tool adapter registration";
        };

        registry = mkOption {
          type = types.listOf (types.submodule {
            options = {
              name = mkOption {
                type = types.str;
                description = "Tool name";
              };

              description = mkOption {
                type = types.str;
                description = "Tool description";
              };

              schema = mkOption {
                type = types.attrs;
                description = "JSON schema for tool parameters";
              };

              handler = mkOption {
                type = types.str;
                description = "Handler endpoint or function";
              };
            };
          });
          default = [];
          description = "Registered tools for this integration";
        };
      };

      # Observability Configuration
      observability = {
        metrics = {
          enable = mkOption {
            type = types.bool;
            default = true;
            description = "Enable Prometheus metrics";
          };

          port = mkOption {
            type = types.port;
            description = "Metrics port (from ports module)";
          };

          path = mkOption {
            type = types.str;
            default = "/metrics";
            description = "Metrics endpoint path";
          };
        };

        logging = {
          level = mkOption {
            type = types.enum [ "debug" "info" "warn" "error" ];
            default = "info";
            description = "Log level";
          };

          format = mkOption {
            type = types.enum [ "json" "text" ];
            default = "json";
            description = "Log format";
          };

          destination = mkOption {
            type = types.str;
            default = "journald";
            description = "Log destination";
          };
        };

        tracing = {
          enable = mkOption {
            type = types.bool;
            default = false;
            description = "Enable distributed tracing";
          };

          endpoint = mkOption {
            type = types.nullOr types.str;
            default = null;
            description = "Tracing endpoint (e.g., Jaeger)";
          };
        };
      };

      # Health Checks
      healthCheck = {
        enable = mkOption {
          type = types.bool;
          default = true;
          description = "Enable health check endpoint";
        };

        path = mkOption {
          type = types.str;
          default = "/health";
          description = "Health check endpoint path";
        };

        interval = mkOption {
          type = types.int;
          default = 30;
          description = "Health check interval in seconds";
        };
      };
    };
  };

in {
  options.mySystem.aiStack.adk = {
    enable = mkEnableOption "Google ADK integrations";

    integrations = mkOption {
      type = types.attrsOf adkIntegrationType;
      default = {};
      description = "ADK integration configurations";
    };

    # Global ADK Configuration
    global = {
      dataDir = mkOption {
        type = types.path;
        default = "/var/lib/adk";
        description = "Global data directory for ADK integrations";
      };

      stateDir = mkOption {
        type = types.path;
        default = "/var/lib/adk/state";
        description = "State directory for ADK integrations";
      };

      cacheDir = mkOption {
        type = types.path;
        default = "/var/cache/adk";
        description = "Cache directory for ADK integrations";
      };
    };
  };

  config = mkIf cfg.enable {
    # Ensure directories exist
    systemd.tmpfiles.rules = [
      "d ${cfg.global.dataDir} 0755 root root -"
      "d ${cfg.global.stateDir} 0755 root root -"
      "d ${cfg.global.cacheDir} 0755 root root -"
    ];
  };
}

# Example Integration Configurations
#
# Example 1: Basic ADK Agent
# mySystem.aiStack.adk.integrations.example-agent = {
#   enable = true;
#   name = "example-adk-agent";
#
#   environment = {
#     baseUrl = "http://127.0.0.1:${toString config.mySystem.ports.exampleAgent}";
#     configFile = /etc/adk/example-agent.json;
#     extraEnv = {
#       ADK_LOG_LEVEL = "debug";
#     };
#   };
#
#   dependencies = {
#     services = [ "ai-hybrid-coordinator.service" ];
#     ports = [ "exampleAgent" "hybridCoordinator" ];
#   };
#
#   a2a = {
#     enable = true;
#     endpoints = {
#       discovery = "/a2a/discover";
#       task = "/a2a/task";
#       event = "/a2a/events";
#       result = "/a2a/result";
#     };
#     agentCard = {
#       name = "Example ADK Agent";
#       version = "1.0.0";
#       capabilities = [ "task_execution" "event_streaming" ];
#       protocols = [ "a2a" "openai" ];
#     };
#   };
#
#   tools = {
#     enable = true;
#     registry = [
#       {
#         name = "search";
#         description = "Search for information";
#         schema = {
#           type = "object";
#           properties = {
#             query = { type = "string"; };
#           };
#           required = [ "query" ];
#         };
#         handler = "/tools/search";
#       }
#     ];
#   };
#
#   observability = {
#     metrics = {
#       enable = true;
#       port = config.mySystem.ports.exampleAgentMetrics;
#       path = "/metrics";
#     };
#     logging = {
#       level = "info";
#       format = "json";
#     };
#   };
#
#   healthCheck = {
#     enable = true;
#     path = "/health";
#     interval = 30;
#   };
# };
#
# Example 2: ADK Agent with Tool Calling
# mySystem.aiStack.adk.integrations.tool-calling-agent = {
#   enable = true;
#   name = "tool-calling-agent";
#
#   environment = {
#     baseUrl = "http://127.0.0.1:${toString config.mySystem.ports.toolCallingAgent}";
#     apiKeyFile = config.age.secrets.adk-api-key.path;
#   };
#
#   a2a = {
#     enable = true;
#     agentCard = {
#       name = "Tool Calling Agent";
#       version = "2.0.0";
#       capabilities = [
#         "tool_calling"
#         "function_execution"
#         "parallel_tools"
#       ];
#     };
#   };
#
#   tools = {
#     enable = true;
#     registry = [
#       {
#         name = "file_read";
#         description = "Read file contents";
#         schema = {
#           type = "object";
#           properties = {
#             path = { type = "string"; };
#           };
#           required = [ "path" ];
#         };
#         handler = "/tools/file/read";
#       }
#       {
#         name = "file_write";
#         description = "Write file contents";
#         schema = {
#           type = "object";
#           properties = {
#             path = { type = "string"; };
#             content = { type = "string"; };
#           };
#           required = [ "path" "content" ];
#         };
#         handler = "/tools/file/write";
#       }
#     ];
#   };
# };
