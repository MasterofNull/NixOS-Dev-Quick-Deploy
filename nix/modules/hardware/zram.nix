{ lib, config, ... }:
let
  cfg = config.mySystem;
in
{
  # zram: compressed in-RAM swap block device.
  # Complements the zswap cache in ram-tuning.nix.  zram provides a dedicated
  # compressed block device backed entirely by RAM; no disk I/O under memory
  # pressure.  On this machine (27 GB) memoryPercent = 30 yields ~8 GB of
  # compressed swap without touching the NVMe.
  # lz4: lower decompression latency than zstd — preferred for AI inference
  # workloads where swap-pressure response time matters more than compression
  # ratio. zstd is better if storage I/O is the bottleneck; lz4 wins when RAM
  # bandwidth is the bottleneck (typical during large model loading).
  zramSwap = lib.mkIf (cfg.hardware.systemRamGb > 4) {
    enable        = true;
    memoryPercent = 30;
    algorithm     = "lz4";
  };
}
