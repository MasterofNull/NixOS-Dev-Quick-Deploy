---
doc_type: design-packet
id: herdr-h1-correction-design-20260815
title: HERDR H1 acceptance correction design
status: active
parent_prd: herdr-h1-correction
date: 2026-08-15
---

# HERDR H1 acceptance correction design

## Frozen predecessor

`ea96bcbfc05fca32d164137fd2cef261f5c68acc` is preserved as the physical H1 implementation commit.
It is not credited as binding acceptance because the independent review completed afterward with
`REQUEST_REVISION`.

## Monotonic correction

This packet supersedes only the original H1 evidence/acceptance ceiling. The behavior-bearing
`flake.nix`, package, Home Manager module, AQ facade, and operations-runbook bytes in `ea96bcbf`
remain byte-identical. The correction intentionally amends the existing test, report, and tracker,
then adds a frozen SPDX SBOM and a new independent review receipt. The accepted H1 hash will be the
additive correction commit, not `ea96bcbf` alone.

## Required evidence

1. `python3 scripts/testing/test-herdr-h1-contract.py` proves hermetic facade/config invariants.
2. `python3 scripts/testing/test-herdr-h1-contract.py --nix-eval` invokes real Nix/Home Manager
   evaluation without activation and proves defaults, rejection, and inert enabled configuration.
3. `nix build --impure --no-link --print-out-paths --expr ...` must terminate successfully.
4. `syft` produces the committed SPDX JSON SBOM, whose digest and generator details are recorded in
   the supply-chain report.
5. Isolated Tier-0 and a fresh independent hash-bound review must pass before the correction commit.

## Reproducible SBOM normalization

Syft `1.44.0` scans the exact pinned source store path. The raw scan is normalized with `jq -S`
before it is admitted as evidence. The normalizer performs these deterministic transforms:

1. set document name to `herdr-0.7.5-source-sbom`;
2. set namespace to
   `https://aq-os.local/sbom/herdr/v0.7.5/ef4c23f5775bb8cfec05f05d0844226ff959a07a`;
3. set `creationInfo.created` to `1970-01-01T00:00:00Z` and sort creators;
4. replace Syft's store-derived document-root ID/name with
   `SPDXRef-Package-herdr-source-root` / `herdr-source-root`, updating relationship endpoints;
5. sort packages and files by SPDX ID, relationships by the complete endpoint/type tuple, external
   references by category/type/locator, checksums by algorithm/value, and all string arrays.

The reproducibility command sequence is:

```bash
syft scan dir:/nix/store/wh5a5fzsd5a1x6wpjln25j54s17as2df-source -o spdx-json > /tmp/H1-SBOM.raw-a.spdx.json
syft scan dir:/nix/store/wh5a5fzsd5a1x6wpjln25j54s17as2df-source -o spdx-json > /tmp/H1-SBOM.raw-b.spdx.json
jq -S -f /tmp/herdr-h1-normalize.jq /tmp/H1-SBOM.raw-a.spdx.json > /tmp/H1-SBOM.normalized-a.spdx.json
jq -S -f /tmp/herdr-h1-normalize.jq /tmp/H1-SBOM.raw-b.spdx.json > /tmp/H1-SBOM.normalized-b.spdx.json
cmp -s /tmp/H1-SBOM.normalized-a.spdx.json /tmp/H1-SBOM.normalized-b.spdx.json
sha256sum /tmp/H1-SBOM.normalized-a.spdx.json
```

`/tmp/herdr-h1-normalize.jq` is the following exact filter (the temporary pathname is not evidence):

```jq
def sort_external_refs:
  if has("externalRefs") then
    .externalRefs |= sort_by(.referenceCategory, .referenceType, .referenceLocator)
  else . end;
def sort_checksums:
  if has("checksums") then
    .checksums |= sort_by(.algorithm, .checksumValue)
  else . end;
def sort_string_array($key):
  if has($key) then .[$key] |= sort else . end;
(.packages[] | select(.SPDXID | contains("DocumentRoot")) | .SPDXID) as $old_root
| "SPDXRef-Package-herdr-source-root" as $new_root
| .name = "herdr-0.7.5-source-sbom"
| .documentNamespace = "https://aq-os.local/sbom/herdr/v0.7.5/ef4c23f5775bb8cfec05f05d0844226ff959a07a"
| .creationInfo.created = "1970-01-01T00:00:00Z"
| .creationInfo.creators |= sort
| .packages |= (map(
    if .SPDXID == $old_root then
      .SPDXID = $new_root | .name = "herdr-source-root"
    else . end
    | sort_external_refs | sort_checksums | sort_string_array("licenseInfoFromFiles")
  ) | sort_by(.SPDXID))
| .files |= (map(
    sort_checksums | sort_string_array("fileTypes") | sort_string_array("licenseInfoInFiles")
  ) | sort_by(.SPDXID))
| .relationships |= (map(
    if .spdxElementId == $old_root then .spdxElementId = $new_root else . end
    | if .relatedSpdxElement == $old_root then .relatedSpdxElement = $new_root else . end
  ) | sort_by(.spdxElementId, .relationshipType, .relatedSpdxElement))
```

Two independent raw scans normalized by this pipeline were byte-identical. The admitted document
SHA-256 is `cfa9a5904c50fdc01ed839bd5f3f827dc6c57ec36e4191e61879900938da715c`.

## Fail-stop rules

Stop on any change to the five frozen behavior-bearing/operations files from `ea96bcbf`, raw HERDR exposure, runtime enablement,
unexpected evaluation side effect, SBOM generator failure, subject drift, or non-PASS review.
