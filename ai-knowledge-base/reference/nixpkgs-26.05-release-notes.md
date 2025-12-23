# Nixpkgs 26.05 Release Notes (Yarara)
**Source:** https://nixos.org/manual/nixpkgs/unstable/release-notes  
**Captured:** 2025-12-23  
**Scope:** Nixpkgs 26.05 (unstable manual; entries may change before release)

## Notable Changes
- `corepack_latest` removed (Corepack no longer distributed with Node.js).
- `spoof` removed (unmaintained; issues on modern OS versions).
- `kanata` now requires `karabiner-dk` 6.0+; `darwinDriver` output stays at the version defined in the package.
- `elegant-sddm` updated for Qt6 compatibility; theme structure changed (see upstream wiki).
- `iroh` removed and split into `iroh-dns-server` and `iroh-relay`.
- Log4Shell scanners removed (unmaintained; vulnerability fixed upstream for years).
- `asio` updated 1.24.0 -> 1.36.0; `asio::io_service` removed in favor of `asio::io_context` (1.33.0). `asio_1_32_0` retained for migration; `asio_1_10` removed. `asio` no longer propagates `boost`.
- `ethercalc` and its module removed (unmaintained; npm install broken).
- `nodePackages.prebuild-install` removed (unmaintained; use upstream alternatives).
- `davis` IMAP auth changes: `IMAP_AUTH_URL` flags split into standalone params:  
  **Before:** `IMAP_AUTH_URL={imap.gmail.com:993/imap/ssl/novalidate-cert}`  
  **After:** `IMAP_AUTH_URL=imap.mydomain.com:993`, `IMAP_ENCRYPTION_METHOD=ssl`, `IMAP_CERTIFICATE_VALIDATION=false`.
- `python3packages.pillow-avif-plugin` removed; functionality is now in `python3packages.pillow` (>= 11.3).
- `uptime-kuma` updated to v2; migration can take hours; backup recommended; corrupt SQLite may require manual fix.
- `fetchPnpmDeps` and `pnpmConfigHook` added as top-level attrs, replacing deprecated `pnpm.fetchDeps` and `pnpm.configHook`.
- `dell-bios-fan-control` package and service added.
- Gradle now uses upstream wrapper script (supports `JAVA_HOME` and `GRADLE_OPTS`).
- `nodejs_latest` now points to `nodejs_25` (was `nodejs_24`).
- `mold` is now wrapped by default.
