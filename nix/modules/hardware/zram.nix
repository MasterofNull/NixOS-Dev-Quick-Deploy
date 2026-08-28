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
    # 2026-08-27 (MEASURED, corrected): for the 24.5GB Qwen3.6-35B on 27GB, LESS
    # zram is better, not more. The 30% (8.2GB) zram was itself consuming ~3.5GB
    # RAM holding compressed swap — RAM the model needed to stay resident; the
    # model ran 8GB-swapped-to-SSD at 3.2 tok/s. After freeing observability +
    # dropping zram, the model became RESIDENT (VmSwap 8GB->71MB) and throughput
    # rose to 5.7 tok/s (1.8x). Since the model wants to be resident, zram competes
    # with it — so keep only a SMALL 10% (~2.7GB) compressed buffer for transient
    # spikes rather than a large pool that steals the model's RAM. (My earlier 50%
    # bump was the wrong direction and failed to allocate at boot anyway.)
    memoryPercent = 10;
    algorithm = "lz4";
  };
}
