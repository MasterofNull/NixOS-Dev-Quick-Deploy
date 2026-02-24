{ ... }:
{
  # TCP BBR congestion control + enlarged socket buffers.
  # Activated unconditionally: improves throughput on all interfaces including
  # the loopback, where AI stack traffic (inference ↔ WebUI ↔ MCP)
  # flows entirely.  BBR sustains higher throughput with lower latency than
  # CUBIC under mild buffer bloat.
  boot.kernelModules = [ "tcp_bbr" ];

  boot.kernel.sysctl = {
    "net.core.default_qdisc"          = "fq";
    "net.ipv4.tcp_congestion_control" = "bbr";

    # Enlarged socket buffers for high-throughput local streams
    # (model inference, Qdrant ingest pipelines).
    "net.core.rmem_max"               = 16777216;
    "net.core.wmem_max"               = 16777216;
    "net.ipv4.tcp_rmem"               = "4096 131072 16777216";
    "net.ipv4.tcp_wmem"               = "4096 65536 16777216";

    # Faster fail-fast for loopback service health checks.
    "net.ipv4.tcp_syn_retries"        = 4;
    "net.ipv4.tcp_synack_retries"     = 2;
  };
}
