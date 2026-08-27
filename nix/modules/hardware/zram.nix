{
  lib,
  config,
  ...
}: let
  cfg = config.mySystem;
in {
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
    # 2026-08-27: raised 30 -> 50 for the 24.5GB Qwen3.6-35B on 27GB. At 30% the
    # 8.2GB zram filled and ~10GB of the model's cold pages spilled to the NVMe
    # SSD swap (~50-100us/access — the 3.2 tok/s throughput wall). A 50% zram
    # (~13.5GB) keeps far more of that swap in compressed RAM (~us decompress, no
    # SSD latency). Tradeoff: zram's compressed data occupies RAM and model
    # weights compress poorly, so this is measured, not assumed — if tok/s doesn't
    # improve it confirms the model simply exceeds 27GB and Q4_K_XL is the fix.
    memoryPercent = 50;
    algorithm = "lz4";
  };
}
