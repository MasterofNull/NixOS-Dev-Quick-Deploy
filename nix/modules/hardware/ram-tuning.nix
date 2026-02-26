{ lib, config, ... }:
let
  cfg = config.mySystem;
  ram = cfg.hardware.systemRamGb;

  # Adaptive Nix build parallelism based on available RAM.
  # Rule: 1 job per 4GB RAM, minimum 2, maximum 16.
  maxJobs = lib.min 16 (lib.max 2 (ram / 4));
  # Each job gets 2 cores up to the physical core count.
  buildCores = lib.min 8 (lib.max 2 (ram / 4));

  # Zswap pool: smaller on RAM-constrained systems (20%), larger otherwise (10%).
  zswapPoolPct = if ram <= 8 then 20 else if ram <= 16 then 15 else 10;

  # zstd is available on all supported kernels in this stack.
  # Avoids "compressor lz4 not available" warnings on some hosts.
  zswapCompressor = "zstd";
  zswapZpool = "zsmalloc";    # Built-in; no extra kernel module needed.
in
{
  # Adaptive Nix build limits (replaces @NIX_BUILD_CORES@ and @NIX_MAX_JOBS@).
  nix.settings = {
    max-jobs = lib.mkDefault maxJobs;
    cores    = lib.mkDefault buildCores;
  };

  # Zswap compressed swap cache + THP mode (Phase 5.1).
  # Combined into one assignment — Nix does not allow duplicate attribute keys.
  boot.kernelParams = lib.mkAfter (
    # Zswap: compressed in-RAM swap cache, scales pool % with available RAM.
    [
      "zswap.enabled=1"
      "zswap.compressor=${zswapCompressor}"
      "zswap.max_pool_percent=${toString zswapPoolPct}"
      "zswap.zpool=${zswapZpool}"
    ]
    # THP madvise: llama.cpp uses madvise(MADV_HUGEPAGE) for model weight buffers.
    # Only beneficial above 4 GB RAM; on ≤4 GB the fragmentation cost dominates.
    ++ lib.optionals (ram > 4) [ "transparent_hugepage=madvise" ]
  );

  # VM pressure tunables adaptive to RAM (replaces @KERNEL_SYSCTL_TUNABLES@ vm.* section).
  boot.kernel.sysctl = {
    "vm.swappiness"             = lib.mkDefault (if ram <= 8 then 60 else if ram <= 16 then 30 else 10);
    "vm.dirty_ratio"            = lib.mkDefault 10;
    "vm.dirty_background_ratio" = lib.mkDefault 5;
    "vm.vfs_cache_pressure"     = lib.mkDefault (if ram <= 8 then 100 else 50);
  };

}
