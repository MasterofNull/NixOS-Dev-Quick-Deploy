#!/usr/bin/env python3
"""Required PR check: independent, head-bound review disposition.

Server-side counterpart of .githooks/commit-msg (which `gh pr merge` bypasses).
Reads the PR body from the GitHub event payload (GITHUB_EVENT_PATH) and passes
only when it carries these `Key: value` lines (same field syntax as commit-msg):

  Review-Disposition: PASS | PASS_WITH_FOLLOWUPS
  Reviewed-subject-sha256: <64 lowercase hex>
  Reviewed-head-sha: <40 lowercase hex>  (must equal the PR head sha)
  Reviewed-by: <lane>                    (must differ from Author-lane)
  Author-lane: <lane>
  Review-Receipt: <repo path>            (receipt minted by scripts/ai/aq-review-receipt
                                          from a real reviewer run; committed in the PR)

The receipt must exist at the PR head, be schema 1, and agree with the body
(head sha, reviewer, author, disposition). Committing the receipt moves the PR
head, so a head that differs from Reviewed-head-sha is also accepted when every
file changed in reviewed..head is under .agent/reviews/receipts/.

Limitations (plain): all lanes share one GitHub account, so identity is
DECLARATIVE. Author-lane/Reviewed-by are self-asserted text; this check proves
a distinct reviewer was claimed and that the claim is bound to the current head
(new content pushes invalidate it; a merge-only update of the base into the
PR branch is accepted when the net change is verbatim-patch-id (whitespace-exact) identical), not that the reviewer is who they say. Reviewed-
subject-sha256 is format-checked only. Receipts raise the bar (fabrication needs
a forged receipt plus a matching registry row and output log, and is detectable
by `aq-review-receipt audit` against the local registry) but are detection-grade,
NOT cryptographic: CI cannot see the local registry and any lane can write the
files. Per-lane signing is tracked in WORKAROUND-REGISTER (WR-REVIEW-1). Uses only the event payload; no secrets or API calls.
"""
import json
import os
import re
import subprocess
import sys

DISPOSITIONS = {"PASS", "PASS_WITH_FOLLOWUPS"}
RECEIPT_PREFIX = ".agent/reviews/receipts/"


def field(body, key):
    """Last `key: value` line, mirroring commit-msg's `sed ... | tail -n 1`."""
    vals = re.findall(rf"^{re.escape(key)}:[ \t]*(.*?)[ \t]*$", body or "", re.M)
    return vals[-1] if vals else ""


def norm(lane):
    return re.sub(r"\s+", " ", lane.strip().lower())


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True, timeout=60).stdout.strip()


def _patch_id(base, commit):
    mb = _git("merge-base", base, commit)
    diff = subprocess.run(["git", "diff", "--binary", mb, commit, "--", ".", f":(exclude){RECEIPT_PREFIX}"], capture_output=True, check=True, timeout=120).stdout
    out = subprocess.run(["git", "patch-id", "--verbatim"], input=diff, capture_output=True, check=True, timeout=60).stdout
    return out.split()[0].decode() if out.split() else ""


def merge_only_update(rhead, head, base):
    """Return (ok, detail): head is a merge-only update of reviewed rhead (fail closed)."""
    try:
        if not base:
            return False, "base sha unavailable"
        try:
            _git("cat-file", "-e", rhead + "^{commit}")
        except (subprocess.CalledProcessError, OSError):
            return False, "reviewed commit unavailable"
        try:
            subprocess.run(["git", "merge-base", "--is-ancestor", rhead, head], check=True, capture_output=True, timeout=60)
        except subprocess.CalledProcessError:
            return False, "reviewed head is not an ancestor of PR head"
        pid_r, pid_h = _patch_id(base, rhead), _patch_id(base, head)
        if not pid_r or not pid_h:
            return False, "empty patch-id"
        if pid_r != pid_h:
            return False, "net change differs from reviewed head"
        # _patch_id excludes the receipt dir, so vet its changes separately.
        rok, rdetail = receipt_only_update(rhead, head, only=False)
        if not rok:
            return False, rdetail
        return True, pid_h
    except (subprocess.SubprocessError, OSError) as exc:
        return False, f"git error: {exc.__class__.__name__}"


def receipt_only_update(rhead, head, only=True):
    """Return (ok, detail): rhead..head only adds/modifies regular *.json receipts (fail closed).

    only=False ignores paths outside RECEIPT_PREFIX (used to vet the receipt dir the patch-id excludes).
    """
    try:
        subprocess.run(["git", "merge-base", "--is-ancestor", rhead, head], check=True, capture_output=True, timeout=60)
        rows = [l for l in _git("diff", "--raw", "--no-renames", "-z", rhead, head).split("\0") if l]
    except (subprocess.SubprocessError, OSError):
        return False, "reviewed commit unavailable or not an ancestor"
    if not rows and only:
        return False, "no changes"
    # -z --raw: ":<srcmode> <dstmode> <srcsha> <dstsha> <status>" then path as the next token.
    for meta, path in zip(rows[0::2], rows[1::2]):
        if not only and not path.startswith(RECEIPT_PREFIX):
            continue
        fields = meta.lstrip(":").split()
        status, dmode = fields[4][:1], fields[1]
        if (status not in ("A", "M") or dmode != "100644" or not path.startswith(RECEIPT_PREFIX)
                or ".." in path.split("/") or not path.endswith(".json")):
            return False, f"non-receipt change: {path}"
    return True, "receipt-only"


def check_receipt(path, head, rhead, reviewer, author, disp):
    """Validate the committed receipt against the body fields; return error list."""
    if not path:
        return ["missing Review-Receipt"]
    if path.startswith("/") or ".." in path.split("/"):
        return ["Review-Receipt must be a repo-relative path"]
    if not head:
        return ["no PR head to read Review-Receipt from"]
    try:
        mode = _git("ls-tree", head, "--", path).split()[0]
        if mode != "100644":
            return [f"Review-Receipt {path} must be a regular file (mode {mode})"]
        r = json.loads(_git("show", f"{head}:{path}"))
    except (subprocess.SubprocessError, OSError, ValueError, IndexError):
        return [f"Review-Receipt {path} not found or not JSON at PR head"]
    if not isinstance(r, dict) or type(r.get("schema")) is not int or r["schema"] != 1:
        return ["Review-Receipt is not schema 1"]
    errs = []
    if type(r.get("pr")) is not int:
        errs.append("receipt pr must be an integer")
    for k in ("run_id", "reviewer_lane", "author_lane", "verdict", "reviewed_head_sha", "output_sha256"):
        v = r.get(k)
        if not isinstance(v, str) or not v.strip():
            errs.append(f"receipt {k} must be a non-empty string")
    if errs:
        return errs
    if not re.fullmatch(r"[0-9a-f]{40}", r["reviewed_head_sha"]):
        errs.append("receipt reviewed_head_sha must be 40 lowercase hex")
    elif r["reviewed_head_sha"] != rhead:
        errs.append("receipt reviewed_head_sha != Reviewed-head-sha")
    if norm(r["reviewer_lane"]) != norm(reviewer):
        errs.append("receipt reviewer_lane != Reviewed-by")
    if norm(r["author_lane"]) != norm(author):
        errs.append("receipt author_lane != Author-lane")
    if r["verdict"] != disp or r["verdict"] == "REQUEST_CHANGES":
        errs.append("receipt verdict != Review-Disposition (or is REQUEST_CHANGES)")
    if not re.fullmatch(r"[0-9a-f]{64}", r["output_sha256"]):
        errs.append("receipt output_sha256 must be 64 lowercase hex")
    return errs


def check(event):
    pr = event.get("pull_request") or {}
    body = (pr.get("body") or "").replace("\r\n", "\n")
    head = (pr.get("head") or {}).get("sha", "")
    base = (pr.get("base") or {}).get("sha", "")
    errors = []
    disp = field(body, "Review-Disposition")
    if not disp:
        errors.append("missing Review-Disposition")
    elif disp not in DISPOSITIONS:
        errors.append(f"Review-Disposition must be PASS or PASS_WITH_FOLLOWUPS (got {disp!r})")
    subj = field(body, "Reviewed-subject-sha256")
    if not subj:
        errors.append("missing Reviewed-subject-sha256")
    elif not re.fullmatch(r"[0-9a-f]{64}", subj):
        errors.append("Reviewed-subject-sha256 must be 64 lowercase hex")
    rhead = field(body, "Reviewed-head-sha")
    if not rhead:
        errors.append("missing Reviewed-head-sha")
    elif not re.fullmatch(r"[0-9a-f]{40}", rhead):
        errors.append("Reviewed-head-sha must be 40 lowercase hex")
    elif rhead != head:
        ok, detail = merge_only_update(rhead, head, base) if head else (False, "no PR head")
        rok, rdetail = receipt_only_update(rhead, head) if head else (False, "no PR head")
        if rok:
            print(f"review rebound: head {head[:12]} only adds review receipts to reviewed {rhead[:12]}")
        elif ok:
            print(f"review rebound: head {head[:12]} is a merge-only update of reviewed {rhead[:12]} "
                  f"(net change identical, verbatim patch-id {detail})")
        else:
            errors.append(f"stale review: Reviewed-head-sha {rhead[:12]} != PR head {head[:12]} ({detail})")
    reviewer = field(body, "Reviewed-by")
    author = field(body, "Author-lane")
    if not reviewer:
        errors.append("missing Reviewed-by")
    if not author:
        errors.append("missing Author-lane")
    if reviewer and author and norm(reviewer) == norm(author):
        errors.append(f"Reviewed-by ({reviewer}) must differ from Author-lane ({author})")
    errors += check_receipt(field(body, "Review-Receipt"), head, rhead, reviewer, author, disp)
    return errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_EVENT_PATH", "")
    if not path:
        print("check-review-disposition: no event payload (GITHUB_EVENT_PATH)", file=sys.stderr)
        return 2
    with open(path, encoding="utf-8") as fh:
        event = json.load(fh)
    errors = check(event)
    if errors:
        print("review-disposition FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("See .github/pull_request_template.md for the required PR body fields.", file=sys.stderr)
        return 1
    print("review-disposition OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
