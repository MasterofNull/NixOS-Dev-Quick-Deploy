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
  # zstd is faster than lz4 at comparable or better compression ratios on AMD.
  zramSwap = lib.mkIf (cfg.hardware.systemRamGb > 4) {
    enable        = true;
    memoryPercent = 30;
    algorithm     = "zstd";
  };
}
