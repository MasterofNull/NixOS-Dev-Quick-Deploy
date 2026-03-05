# Build Performance Optimizations

## Recent Improvements (Latest Update)

**CRITICAL FIX**: Binary caches now work correctly during initial deployment!

Previous versions had a critical bug where binary cache settings were only applied AFTER the first build completed. This meant the initial deployment compiled everything from source, even when you selected "Use Binary Caches".

**What was fixed:**
- ✅ Binary cache flags now passed directly to `nixos-rebuild` commands
- ✅ Parallel build settings (`max-jobs=auto`, `cores=0`) applied during initial build
- ✅ Network timeouts increased for large package downloads (10s connect, 300s stalled)
- ✅ `joserfc` package test failure workaround added (skips flaky tests)
- ✅ `builders-use-substitutes` now enabled during the build itself

**Expected improvement:** Initial deployment with binary caches should now be **3-5x faster** (20-40 minutes instead of 60-120 minutes).

---

## Overview

The NixOS Quick Deploy script gives you the choice between three build strategies:

1. **Binary Caches (Recommended)** - Downloads pre-built packages: **20-40 minutes**
2. **Build from Source** - Compiles locally: **60-120 minutes**
3. **Remote Builders / Private Cachix** - Inherits the binary cache defaults and layers in your own SSH build farm definitions and authenticated Cachix caches.

You'll be prompted to choose during installation. This guide explains both options and their trade-offs.

## Making Your Choice

During the deployment, you'll see this prompt:

```
Build Performance Strategy

Choose your build strategy:

  1) Use Binary Caches (RECOMMENDED)
     - Downloads pre-built packages from trusted sources
     - Estimated time: 20-40 minutes
     - Requires good internet connection (~2-4 GB download)
     - Lower CPU and memory usage
     - Caches: NixOS official, nix-community, CUDA, devenv

  2) Build from Source
     - Compiles all packages locally from source code
     - Estimated time: 60-120 minutes
     - Minimal downloads (~500 MB source code)
     - High CPU and memory usage during compilation
     - Full control over build process

  3) Remote Builders or Private Cachix
     - Starts with the binary cache defaults
     - Lets you register SSH build machines (e.g., `ssh://nix@builder x86_64-linux - 6 1`)
     - Optionally enables authenticated Cachix caches (requires token)
     - Ideal for low-power devices that can offload builds

Choose build strategy (1-3) [1]:
```

**When to choose Binary Caches:**
- You have decent internet (25+ Mbps recommended)
- You want the fastest deployment
- You trust the NixOS community caches
- You're on a laptop or limited resources

**When to choose Build from Source:**
- You have slow/metered internet
- You want full control over compilation
- You have a powerful CPU and time to spare
- You're building for security-critical applications

**When to choose Remote Builders / Private Cachix:**
- You maintain trusted build machines reachable over SSH
- You already operate private Cachix caches and want to reuse them
- The target host is resource-constrained but has reliable network access
- You need to keep sensitive derivations out of public caches

After selecting option 3, the script will prompt for:

- One or more **builder specifications** (format: `ssh://user@host system - max-jobs speed`). Paste each builder line and press Enter on an empty line to finish.
- Optional **SSH private key path** (defaults to `~/.ssh/id_ed25519`).
- Additional `ssh` options (for non-standard ports, jump hosts, etc.).
- A list of **private Cachix cache names** and whether to authenticate them.
- A **Cachix auth token** when authentication is requested.

Inputs are stored in `$STATE_DIR/preferences/remote-builders.env` so you only have to enter them once per machine. Subsequent runs reuse the saved configuration automatically (you can edit or delete the file to change the answers later).

## Optimizations Applied

### 1. Binary Caches (Substituters)

**Applies when:** You choose option 1 during deployment

**What it does:** Downloads pre-built packages instead of compiling from source

**Configuration added:**
```nix
substituters = [
  "https://cache.nixos.org"           # Official NixOS cache
  "https://nix-community.cachix.org"  # Community packages (COSMIC, AI tools)
  "https://cuda-maintainers.cachix.org"  # CUDA packages (NVIDIA)
  "https://devenv.cachix.org"         # Development environments
];
```

**Impact:**
- Reduces build time by **60-80%** for most packages
- COSMIC desktop: ~45 min → ~5 min
- gpt4all: ~15 min → ~2 min (when cached)
- Python packages: ~20 min → ~3 min

### 2. Parallel Builds

**What it does:** Utilizes all CPU cores for maximum build throughput

**Configuration added:**
```nix
max-jobs = "auto";  # Run multiple builds simultaneously
cores = 0;          # Each build uses all available cores
```

**Impact:**
- On 4-core CPU: **2-3x faster** builds
- On 8-core CPU: **3-4x faster** builds
- On 16-core CPU: **4-6x faster** builds

### 3. Builder Substitutes

**What it does:** Downloads dependencies during builds instead of waiting

**Configuration added:**
```nix
builders-use-substitutes = true;
```

**Impact:**
- Reduces sequential wait times
- **15-20%** faster overall builds

### 4. Build Artifact Retention

**What it does:** Keeps build outputs and derivations for faster rebuilds

**Configuration added:**
```nix
keep-outputs = true;
keep-derivations = true;
```

**Impact:**
- Subsequent builds: **50-70%** faster
- Switching configurations: Nearly instant

## Expected Build Times

### First-Time Installation

| Component | Before | After | Improvement |
|-----------|--------|-------|-------------|
| System packages | 20-30 min | 5-10 min | **70%** faster |
| COSMIC Desktop | 40-50 min | 5-10 min | **85%** faster |
| AI Tools (gpt4all, ollama) | 30-40 min | 5-15 min | **75%** faster |
| Python AI environment | 15-25 min | 3-5 min | **80%** faster |
| **Total** | **90-120 min** | **20-40 min** | **65-75%** faster |

*Note: Times vary based on internet speed, CPU cores, and binary cache availability*

### Subsequent Builds/Updates

| Operation | Before | After | Improvement |
|-----------|--------|-------|-------------|
| Small config changes | 5-10 min | 30-90 sec | **85%** faster |
| Package updates | 20-40 min | 3-8 min | **80%** faster |
| Full system rebuild | 60-90 min | 10-20 min | **80%** faster |

## Network Considerations

### Internet Speed Impact

- **Fast (100+ Mbps):** Binary cache downloads are nearly instant
- **Medium (25-100 Mbps):** Downloading binaries still much faster than building
- **Slow (<25 Mbps):** Consider building locally for small packages, use cache for large ones

### Data Usage

First-time installation downloads approximately:
- **Without caches:** ~500 MB source + compilation
- **With caches:** ~2-4 GB pre-built binaries

*Trade-off: More bandwidth for less time and CPU usage*

## Additional Optimizations

### For Slower Machines

If you have a slower CPU or limited RAM, consider:

1. **Reduce parallelism:**
   ```nix
   max-jobs = 2;  # Limit concurrent builds
   cores = 2;     # Limit cores per build
   ```

2. **Increase swap:**
   ```nix
   zramSwap.memoryPercent = 150;  # More compressed swap
   ```

3. **Use more caches:**
   ```bash
   # Add your own cachix cache
   cachix use <your-cache-name>
   ```

### For Faster Machines

If you have a high-end CPU (12+ cores):

1. **Increase parallelism:**
   ```nix
   max-jobs = 16;  # More concurrent builds
   ```

2. **Use local cache:**
   ```bash
   # Set up a local binary cache for rebuilds
   nix-serve -p 5000
   ```

## Monitoring Build Performance

### Check What's Being Downloaded vs Built

```bash
# During a build, check what's happening
nix build --dry-run .#nixosConfigurations.$(hostname).config.system.build.toplevel

# See which packages will be built vs downloaded
# "will be built" = source compilation
# "will be fetched" = binary download
```

### View Build Logs

```bash
# For the last build
nix log /nix/store/<drv-path>

# For a specific package
nix log nixpkgs#gpt4all
```

### Benchmark Your System

```bash
# Time a full rebuild
time sudo nixos-rebuild switch --flake .

# Time a home-manager rebuild
time home-manager switch --flake .#$(whoami)
```

## Troubleshooting Slow Builds

### Issue: Still building from source

**Symptoms:** Seeing "building" instead of "fetching" for common packages

**Solutions:**
1. Check cache availability:
   ```bash
   nix-channel --update
   nix flake update  # Update flake inputs
   ```

2. Verify cache configuration:
   ```bash
   nix show-config | grep substituters
   ```

3. Clear cache and retry:
   ```bash
   nix-collect-garbage -d
   nix-store --gc
   ```

### Issue: Network timeouts

**Symptoms:** "unable to download" errors

**Solutions:**
1. Increase timeout:
   ```nix
   nix.settings = {
     connect-timeout = 10;  # Increase from default 5
     stalled-download-timeout = 600;  # 10 minutes
   };
   ```

2. Use fallback cache:
   ```nix
   nix.settings.fallback = true;
   ```

### Issue: High memory usage

**Symptoms:** System freezing during builds

**Solutions:**
1. Reduce parallelism (see "For Slower Machines" above)

2. Monitor memory:
   ```bash
   watch -n 1 free -h
   htop  # Shows per-process memory usage
   ```

3. Increase swap:
   ```bash
   sudo swapoff -a
   sudo dd if=/dev/zero of=/swapfile bs=1G count=8
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

## Cache Maintenance

### Clear Old Build Artifacts

```bash
# Delete everything older than 7 days
nix-collect-garbage --delete-older-than 7d

# Delete everything except current system
nix-collect-garbage -d

# Optimize store (deduplicate)
nix-store --optimise
```

### Pre-download Dependencies

```bash
# Before starting a long build, pre-download everything
nix-store -r /nix/store/$(nix-instantiate '<nixpkgs>' -A system)

# Or for a specific package
nix-build '<nixpkgs>' -A gpt4all --dry-run
```

## Changing Your Choice Later

If you want to switch between binary caches and source builds after installation:

### Enable Binary Caches (if you chose source builds)

Edit your configuration:
```bash
sudo nano ~/.dotfiles/home-manager/configuration.nix
```

Find the `nix.settings` section and replace it with:
```nix
nix.settings = {
  experimental-features = [ "nix-command" "flakes" ];
  auto-optimise-store = true;
  trusted-users = [ "root" "@wheel" ];
  allowed-users = [ "@wheel" ];

  # Enable binary caches
  max-jobs = "auto";
  cores = 0;
  substituters = [
    "https://cache.nixos.org"
    "https://nix-community.cachix.org"
    "https://cuda-maintainers.cachix.org"
    "https://devenv.cachix.org"
  ];
  trusted-public-keys = [
    "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
    "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs="
    "cuda-maintainers.cachix.org-1:0dq3bujKpuEPMCX6U4WylrUDZ9JyUG0VpVZa7CNfq5E="
    "devenv.cachix.org-1:w1cLUi8dv3hnoSPGAuibQv+f9TZLr6cv/Hm9XgU50cw="
  ];
  builders-use-substitutes = true;
  keep-outputs = true;
  keep-derivations = true;
  fallback = true;
  warn-dirty = false;
};
```

Then rebuild:
```bash
sudo nixos-rebuild switch --flake ~/.dotfiles/home-manager
```

### Disable Binary Caches (switch to source builds)

Edit the same file and simplify to:
```nix
nix.settings = {
  experimental-features = [ "nix-command" "flakes" ];
  auto-optimise-store = true;
  trusted-users = [ "root" "@wheel" ];
  allowed-users = [ "@wheel" ];

  # Build from source (with parallelism)
  max-jobs = "auto";
  cores = 0;
  substituters = [ "https://cache.nixos.org" ];  # Only official cache
  trusted-public-keys = [ "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY=" ];
  warn-dirty = false;
};
```

## Comparison: Source vs Binary Caches

### Build from Source Configuration
```nix
nix.settings = {
  experimental-features = [ "nix-command" "flakes" ];
  auto-optimise-store = true;
  max-jobs = "auto";
  cores = 0;
  substituters = [ "https://cache.nixos.org" ];  # Only official cache
  trusted-public-keys = [ "cache.nixos.org-1:..." ];
};
```

**Result:** Most packages build from source, only core NixOS packages use cache

### Binary Cache Configuration
```nix
nix.settings = {
  experimental-features = [ "nix-command" "flakes" ];
  auto-optimise-store = true;
  max-jobs = "auto";
  cores = 0;
  substituters = [ /* 4 caches */ ];
  trusted-public-keys = [ /* 4 keys */ ];
  builders-use-substitutes = true;
  keep-outputs = true;
  keep-derivations = true;
  fallback = true;
};
```

**Result:** Pre-built binaries downloaded in parallel, minimal source compilation

## Further Reading

- [Nix Binary Caches](https://nixos.wiki/wiki/Binary_Cache)
- [Cachix Documentation](https://docs.cachix.org/)
- [Nix Build Performance](https://nixos.org/manual/nix/stable/command-ref/conf-file.html)
- [NixOS Build Options](https://search.nixos.org/options?query=nix.settings)

## Contributing

If you discover additional optimizations or find better cache configurations, please submit a PR or open an issue!
