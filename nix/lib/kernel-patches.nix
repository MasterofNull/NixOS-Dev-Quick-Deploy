# Kernel Patch Management Library
# Provides utilities for fetching, validating, and tracking kernel patches.
#
# Usage:
#   let
#     patchLib = import ./kernel-patches.nix { inherit lib pkgs; };
#     patch = patchLib.fetchKernelPatch {
#       name = "cve-2026-12345-fix";
#       url = "https://lore.kernel.org/...";
#       sha256 = "...";
#     };
#   in ...
{ lib, pkgs }:

let
  # Known kernel mailing lists for patch sourcing
  knownMailingLists = {
    lkml = "lore.kernel.org/linux-kernel";
    netdev = "lore.kernel.org/netdev";
    dri-devel = "lore.kernel.org/dri-devel";
    linux-fsdevel = "lore.kernel.org/linux-fsdevel";
    linux-security = "lore.kernel.org/linux-security-module";
    linux-hardening = "lore.kernel.org/linux-hardening";
    linux-mm = "lore.kernel.org/linux-mm";
  };

  # Kernel subsystem to mailing list mapping
  subsystemToList = {
    drm = "dri-devel";
    net = "netdev";
    fs = "linux-fsdevel";
    mm = "linux-mm";
    security = "linux-security";
    hardening = "linux-hardening";
  };

in rec {
  # Fetch a patch from a URL with validation
  fetchKernelPatch = {
    name,
    url,
    sha256,
    stripComponents ? 1,
    revert ? false,
    extraCmds ? "",
  }: pkgs.fetchpatch {
    inherit name url sha256 stripComponents revert;
    postFetch = ''
      # Validate patch format
      if ! grep -q "^diff --git" "$out" && ! grep -q "^---" "$out"; then
        echo "WARNING: ${name} may not be a valid patch format" >&2
      fi
      ${extraCmds}
    '';
  };

  # Fetch a patch from kernel.org git
  fetchKernelOrgPatch = {
    name,
    commit,
    sha256,
    repo ? "torvalds/linux",
  }: fetchKernelPatch {
    inherit name sha256;
    url = "https://git.kernel.org/pub/scm/linux/kernel/git/${repo}.git/patch/?id=${commit}";
  };

  # Fetch a patch from lore.kernel.org
  fetchLorePatch = {
    name,
    messageId,
    sha256,
    list ? "linux-kernel",
  }: let
    baseUrl = if builtins.hasAttr list knownMailingLists
              then "https://${knownMailingLists.${list}}"
              else "https://lore.kernel.org/${list}";
  in fetchKernelPatch {
    inherit name sha256;
    url = "${baseUrl}/${messageId}/raw";
  };

  # Create a CVE fix patch record
  mkCVEPatch = {
    cveId,
    name ? "cve-${lib.toLower cveId}-fix",
    url ? null,
    commit ? null,
    sha256,
    subsystems ? [],
    description ? "Fix for ${cveId}",
    severity ? "unknown",
  }: assert url != null || commit != null;
  {
    inherit name sha256 subsystems description severity;
    cveIds = [ cveId ];
    url = if url != null then url
          else "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/patch/?id=${commit}";
  };

  # Create a security hardening patch record
  mkHardeningPatch = {
    name,
    url ? null,
    commit ? null,
    sha256,
    subsystems ? [ "hardening" ],
    description,
  }: assert url != null || commit != null;
  {
    inherit name sha256 subsystems description;
    cveIds = [];
    url = if url != null then url
          else "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/patch/?id=${commit}";
  };

  # Validate a list of patches
  validatePatches = patches:
    builtins.all (patch:
      (patch ? name) &&
      (patch ? sha256) &&
      ((patch ? url) || (patch ? path))
    ) patches;

  # Group patches by subsystem
  groupBySubsystem = patches:
    lib.groupBy (patch:
      if patch.subsystems == [] then "other"
      else builtins.head patch.subsystems
    ) patches;

  # Extract CVE IDs from a list of patches
  extractCVEIds = patches:
    lib.unique (lib.flatten (map (p: p.cveIds or []) patches));

  # Generate a patch manifest for tracking
  generatePatchManifest = { kernelVersion, patches }: {
    version = "1.0";
    kernel = kernelVersion;
    generated = builtins.currentTime or 0;
    patches = map (patch: {
      name = patch.name;
      cveIds = patch.cveIds or [];
      subsystems = patch.subsystems or [];
      sha256 = patch.sha256;
    }) patches;
    summary = {
      totalPatches = builtins.length patches;
      cveCount = builtins.length (extractCVEIds patches);
      subsystems = lib.unique (lib.flatten (map (p: p.subsystems or []) patches));
    };
  };

  # Common CVE patch sources (can be extended)
  knownCVESources = {
    nvd = "https://nvd.nist.gov/vuln/detail/";
    cveOrg = "https://www.cve.org/CVERecord?id=";
    kernelCVE = "https://www.cvedetails.com/cve/";
    cisaKev = "https://www.cisa.gov/known-exploited-vulnerabilities-catalog";
  };

  # Helper to construct CVE detail URL
  cveDetailUrl = { cveId, source ? "nvd" }:
    "${knownCVESources.${source}}${cveId}";

  # Fetch patches for specific kernel version from stable tree
  fetchStablePatches = { version, fromVersion, sha256 }:
    let
      majorMinor = builtins.concatStringsSep "." (lib.take 2 (lib.splitString "." version));
    in fetchKernelPatch {
      name = "stable-${fromVersion}-to-${version}";
      url = "https://cdn.kernel.org/pub/linux/kernel/v${builtins.head (lib.splitString "." version)}.x/patch-${version}.xz";
      inherit sha256;
    };

  # Check if a patch applies to a given kernel version
  patchAppliesTo = { patch, kernelVersion }:
    let
      patchVersions = patch.kernelVersions or [];
    in
      if patchVersions == [] then true
      else builtins.any (v:
        lib.hasPrefix v kernelVersion || kernelVersion == v
      ) patchVersions;

  # Filter patches applicable to a kernel version
  filterApplicablePatches = { patches, kernelVersion }:
    builtins.filter (p: patchAppliesTo { patch = p; inherit kernelVersion; }) patches;
}
