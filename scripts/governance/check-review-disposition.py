#!/usr/bin/env python3
"""Required PR check: independent, head-bound review disposition.

Server-side counterpart of .githooks/commit-msg (which `gh pr merge` bypasses).
Takes the PR number and repository from the event payload (immutable), then reads
the CURRENT head sha, base sha and body from the GitHub API, so a push/edit race
or a re-run sees live state, not the frozen payload. If the API cannot be read
the check fails closed. It passes only when the body carries these `Key: value`
lines (same field syntax as commit-msg):

  Review-Disposition: PASS | PASS_WITH_FOLLOWUPS
  Reviewed-subject-sha256: <64 lowercase hex>
  Reviewed-head-sha: <40 lowercase hex>  (must equal the PR head sha)
  Reviewed-by: <lane>                    (must differ from Author-lane)
  Author-lane: <lane>
  Review-Receipt: <repo path>            (LEGACY only: receipt committed in the PR)

Receipt, current form: fetched at run time from the append-only `review-receipts`
branch (receipts/pr<N>-<head12>.json, schema 2, published by `aq-review-receipt
publish`), so issuing it never changes the PR head. It must bind this repo, this
PR, Reviewed-head-sha and that commit's tree, name a non-author reviewer and agree
with the body (reviewer, author, disposition). A head that differs from
Reviewed-head-sha is accepted only under the existing merge-only / receipt-only
rules. Receipt missing or malformed, or a branch that cannot be fetched, fails.

Legacy form (migration): a schema 1 receipt committed under .agent/reviews/receipts/
named by Review-Receipt still validates, but only for the frozen cohort of PRs numbered
<= LEGACY_MAX_PR, only when NO off-branch receipt exists (true absence: branch or file
not there), and only if the receipt's `pr` equals this PR. Schema 1 carries no repo
field, so a legacy receipt cannot be bound to this repository; that limit is why the
fallback is frozen and is removed once the cohort has closed. A receipt that cannot be
read (fetch error, malformed JSON, non-object JSON, non-regular file) is a failure and
never falls through to the legacy path. An off-branch receipt, when present, takes
precedence and must itself be valid. Retirement plan: the LEGACY_MAX_PR fallback and the
receipt-only rule are removed in S3, when the landing tool switches to off-branch
receipts; no time limit is added to the legacy path before then.

Accepted limits: validation and result publication are not atomic, so a mutation after
the final metadata read is possible; a clean merge from trusted main can carry unreviewed
semantic interactions (the limit of the merge-exemption policy); and the same-second
push/edit ordering on GitHub is validated on the live PR, not by the unit tests.

Head binding: the run must evaluate the head of its own event. If the live head differs
from the event's head the run fails as stale (the run for the new head decides); after
the receipt is read the PR metadata is read again and any change of head or body fails.

The PR must target `main` of this repository (live base.ref and base repo, read twice;
base ref, repo and sha must not change between reads). A head that differs from
Reviewed-head-sha is accepted only when every commit on the
first-parent chain head..Reviewed-head-sha is either (a) a merge whose second parent is
an ancestor of the tip of origin's `refs/heads/main`, fetched by this run and never
taken from the API's base sha, and whose tree equals the clean automatic result of
`git merge-tree --write-tree <first-parent> <second-parent>` (needs git >= 2.38; the
runner image's git is checked at run time and the check fails closed if it is older), or
(b) for legacy-cohort PRs only, a commit that merely adds/modifies receipt JSON files
under .agent/reviews/receipts/. Conflicted or hand-edited merges and ordinary commits
need a new review.

Limitations (plain): all lanes share one GitHub account, so identity is
DECLARATIVE. Author-lane/Reviewed-by are self-asserted text; this check proves
a distinct reviewer was claimed and that the claim is bound to the current head
(new content pushes invalidate it; a merge-only update of the base into the
PR branch is accepted only when it is a clean automatic merge, see above), not that the reviewer is who they say. Reviewed-
subject-sha256 is format-checked only. Receipts raise the bar (fabrication needs
a forged receipt plus a matching registry row and output log, and is detectable
by `aq-review-receipt audit` against the local registry) but are detection-grade,
NOT cryptographic: CI cannot see the local registry and any lane can write the
files. Per-lane signing is tracked in WORKAROUND-REGISTER (WR-REVIEW-1). Off-branch receipts are no stronger: any lane holding the shared token can push
to review-receipts (Design Decision 4); the upgrade path is a separate issuer identity.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

DISPOSITIONS = {"PASS", "PASS_WITH_FOLLOWUPS"}
RECEIPT_PREFIX = ".agent/reviews/receipts/"
RECEIPT_BRANCH = "review-receipts"
# Frozen migration cohort: PRs numbered above this need an off-branch (schema 2) receipt.
# Remove the schema 1 fallback entirely once every PR <= this number has closed.
LEGACY_MAX_PR = 720
FETCH_REMOTE = "origin"
TRUSTED_BASE_REF = "main"
POLICY_VERSION = "review-receipts/1"
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")


def field(body, key):
    """Last `key: value` line, mirroring commit-msg's `sed ... | tail -n 1`."""
    vals = re.findall(rf"^{re.escape(key)}:[ \t]*(.*?)[ \t]*$", body or "", re.M)
    return vals[-1] if vals else ""


def norm(lane):
    return re.sub(r"\s+", " ", lane.strip().lower())


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True, timeout=60).stdout.strip()


def _is_ancestor(a, b):
    r = subprocess.run(["git", "merge-base", "--is-ancestor", a, b], capture_output=True, timeout=60)
    if r.returncode not in (0, 1):
        raise subprocess.SubprocessError("merge-base failed")
    return r.returncode == 0


def merge_only_update(rhead, head, base, legacy=True):
    """Return (ok, detail): head is reviewed rhead plus clean automatic merges of the base (fail closed)."""
    try:
        if not base:
            return False, "base sha unavailable"
        try:
            _git("cat-file", "-e", rhead + "^{commit}")
        except (subprocess.CalledProcessError, OSError):
            return False, "reviewed commit unavailable"
        if not _is_ancestor(rhead, head):
            return False, "reviewed head is not an ancestor of PR head"
        try:
            _git("cat-file", "-e", base + "^{commit}")
        except (subprocess.CalledProcessError, OSError):
            try:
                subprocess.run(["git", "fetch", "--no-tags", "-q", FETCH_REMOTE, base], capture_output=True, check=True, timeout=180)
                _git("cat-file", "-e", base + "^{commit}")
            except (subprocess.SubprocessError, OSError):
                return False, "base commit unavailable"
        cur = head
        for _ in range(500):
            if cur == rhead:
                return True, "merge-only"
            parents = _git("rev-list", "--parents", "-n1", cur).split()[1:]
            if len(parents) == 1 and legacy:
                rok, rdetail = receipt_only_update(parents[0], cur)
                if not rok:
                    return False, f"net change differs from reviewed head (non-merge commit {cur[:12]}: {rdetail})"
                cur = parents[0]
                continue
            if len(parents) != 2:
                return False, f"net change differs from reviewed head (non-merge commit {cur[:12]} or reviewed head off the first-parent chain)"
            first, other = parents
            if not _is_ancestor(other, base):
                return False, f"merge {cur[:12]} brings in a commit that is not in the base branch"
            mt = subprocess.run(["git", "merge-tree", "--write-tree", "--no-messages", first, other],
                                capture_output=True, text=True, timeout=120)
            if mt.returncode == 1:
                return False, f"net change differs from reviewed head (merge {cur[:12]} conflicts when redone)"
            if mt.returncode != 0 or not HEX40.fullmatch(mt.stdout.split("\n")[0].strip()):
                return False, "git merge-tree --write-tree unavailable or failed (needs git >= 2.38)"
            if mt.stdout.split("\n")[0].strip() != _git("rev-parse", f"{cur}^{{tree}}"):
                return False, f"net change differs from reviewed head (merge {cur[:12]} is not the automatic merge result)"
            cur = first
        return False, "too many commits since the reviewed head"
    except (subprocess.SubprocessError, OSError):
        return False, "git error while checking merge-only update"


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


def check_receipt(path, head, rhead, reviewer, author, disp, pr_number=None):
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
    if pr_number is not None and r["pr"] != pr_number:
        errs.append(f"legacy receipt pr {r['pr']} != {pr_number} (replay)")
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



def check_offbranch_receipt(r, repo, pr_number, rhead, reviewer, author, disp):
    """Validate a schema 2 receipt from the review-receipts branch; return error list."""
    if not isinstance(r, dict) or type(r.get("schema")) is not int or r["schema"] != 2:
        return ["off-branch receipt is not schema 2"]
    errs = []
    if type(r.get("pr")) is not int:
        errs.append("receipt pr must be an integer")
    for k in ("repo", "run_id", "reviewer_lane", "author_lane", "verdict", "reviewed_head_sha",
              "tree", "base_commit", "policy_version", "output_sha256"):
        v = r.get(k)
        if not isinstance(v, str) or not v.strip():
            errs.append(f"receipt {k} must be a non-empty string")
    if errs:
        return errs
    if r["repo"] != repo:
        errs.append(f"receipt repo {r['repo']!r} != {repo!r} (replay)")
    if r["pr"] != pr_number:
        errs.append(f"receipt pr {r['pr']} != {pr_number} (replay)")
    if r["policy_version"] != POLICY_VERSION:
        errs.append(f"receipt policy_version {r['policy_version']!r} != {POLICY_VERSION!r}")
    for k in ("reviewed_head_sha", "tree", "base_commit"):
        if not HEX40.fullmatch(r[k]):
            errs.append(f"receipt {k} must be 40 lowercase hex")
    if not HEX64.fullmatch(r["output_sha256"]):
        errs.append("receipt output_sha256 must be 64 lowercase hex")
    if errs:
        return errs
    if r["reviewed_head_sha"] != rhead:
        errs.append("receipt reviewed_head_sha != Reviewed-head-sha")
    try:
        tree = _git("rev-parse", f"{rhead}^{{tree}}")
        if tree != r["tree"]:
            errs.append("receipt tree != tree of reviewed head")
    except (subprocess.SubprocessError, OSError):
        errs.append("reviewed head tree unavailable")
    if norm(r["reviewer_lane"]) != norm(reviewer):
        errs.append("receipt reviewer_lane != Reviewed-by")
    if norm(r["author_lane"]) != norm(author):
        errs.append("receipt author_lane != Author-lane")
    if norm(r["reviewer_lane"]) == norm(r["author_lane"]):
        errs.append("receipt reviewer_lane == author_lane (self-review)")
    if r["verdict"] != disp or r["verdict"] == "REQUEST_CHANGES":
        errs.append("receipt verdict != Review-Disposition (or is REQUEST_CHANGES)")
    return errs


def load_offbranch_receipt(remote, pr_number, rhead):
    """Fetch review-receipts and read this PR/head receipt: (receipt|None, error|None).

    None+None means the branch or file is absent; any fetch/parse problem is an error (fail closed).
    """
    path = f"receipts/pr{pr_number}-{rhead[:12]}.json"
    try:
        listing = subprocess.run(["git", "ls-remote", remote, f"refs/heads/{RECEIPT_BRANCH}"],
                                 capture_output=True, text=True, timeout=120)
        if listing.returncode != 0:
            return None, f"cannot reach {RECEIPT_BRANCH} on {remote}: {listing.stderr.strip()[:200]}"
        if not listing.stdout.strip():
            return None, None
        subprocess.run(["git", "fetch", "--no-tags", "-q", remote, f"refs/heads/{RECEIPT_BRANCH}"],
                       capture_output=True, text=True, check=True, timeout=180)
        tip = _git("rev-parse", "FETCH_HEAD")
        try:
            mode = _git("ls-tree", tip, "--", path).split()[0]
        except IndexError:
            return None, None
        if mode != "100644":
            return None, f"{path} on {RECEIPT_BRANCH} must be a regular file (mode {mode})"
        data = json.loads(_git("show", f"{tip}:{path}"))
        if not isinstance(data, dict):
            return None, f"{path} on {RECEIPT_BRANCH} is not a JSON object"
        return data, None
    except (subprocess.SubprocessError, OSError, ValueError) as exc:
        return None, f"cannot read {RECEIPT_BRANCH}: {exc.__class__.__name__}"


def check(event, receipt_loader=None):
    """Return the error list. receipt_loader(pr_number, rhead) -> (receipt|None, error|None) enables
    the off-branch path; without it only legacy committed receipts are accepted."""
    pr = event.get("pull_request") or {}
    body = (pr.get("body") or "").replace("\r\n", "\n")
    head = (pr.get("head") or {}).get("sha", "")
    base = (pr.get("base") or {}).get("sha", "")
    repo = (event.get("repository") or {}).get("full_name", "")
    pr_number = pr.get("number", event.get("number"))
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
        legacy_ok = pr_number is None or (type(pr_number) is int and pr_number <= LEGACY_MAX_PR)
        ok, detail = merge_only_update(rhead, head, base, legacy_ok) if head else (False, "no PR head")
        rok, rdetail = receipt_only_update(rhead, head) if head and legacy_ok else (False, "no PR head" if not head else "receipt-only updates apply to the legacy cohort only")
        if rok:
            print(f"review rebound: head {head[:12]} only adds review receipts to reviewed {rhead[:12]}")
        elif ok:
            print(f"review rebound: head {head[:12]} is a merge-only update of reviewed {rhead[:12]} "
                  f"(clean automatic merge of the base, {detail})")
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
    legacy = field(body, "Review-Receipt")
    r, rerr = (None, None)
    if receipt_loader and HEX40.fullmatch(rhead or ""):
        if type(pr_number) is not int or not repo:
            errors.append("event lacks repository/PR number; cannot locate off-branch receipt")
        else:
            r, rerr = receipt_loader(pr_number, rhead)
    if r is not None:
        errors += check_offbranch_receipt(r, repo, pr_number, rhead, reviewer, author, disp)
    elif rerr:
        errors.append(rerr)  # unreadable receipt is a failure, never a reason to try the legacy path
    elif legacy:
        if type(pr_number) is int and pr_number > LEGACY_MAX_PR:
            errors.append(f"PR {pr_number} is past the legacy cohort (<= {LEGACY_MAX_PR}); publish an off-branch receipt to {RECEIPT_BRANCH}")
        else:
            errors += check_receipt(legacy, head, rhead, reviewer, author, disp, pr_number)
    elif receipt_loader:
        errors.append(f"missing receipt: none on {RECEIPT_BRANCH} for PR {pr_number} head {(rhead or '')[:12]}")
    else:
        errors.append("missing Review-Receipt")
    return errors


def api_get(url, token, timeout=30):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "check-review-disposition"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as resp:
        return json.load(resp)


def _read_live(get, url, repo):
    """Return (head, base_sha, body, base_ref, base_repo); the PR must target this repo's main."""
    live = get(url)
    head, base = live["head"]["sha"], live["base"]["sha"]
    ref, brepo = live["base"]["ref"], live["base"]["repo"]["full_name"]
    body = live.get("body") or ""
    if not isinstance(body, str) or not HEX40.fullmatch(head or "") or not HEX40.fullmatch(base or "") \
            or not isinstance(ref, str) or not isinstance(brepo, str):
        raise ValueError("unexpected PR payload")
    return head, base, body, ref, brepo


def _base_problem(state, repo):
    if state[3] != TRUSTED_BASE_REF or state[4].lower() != repo.lower():
        return (f"PR targets {state[4]}:{state[3]}; only {repo}:{TRUSTED_BASE_REF} is accepted "
                "(a merge-only update is judged against that branch alone)")
    return None


def evaluate(event, get=None, remote="origin", fetch_head=True):
    """Run the check against LIVE PR state for the head this run was started for; fail closed otherwise."""
    global FETCH_REMOTE
    FETCH_REMOTE = remote
    get = get or (lambda url: api_get(url, os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")))
    pr0 = event.get("pull_request") or {}
    repo = (event.get("repository") or {}).get("full_name") or os.environ.get("GITHUB_REPOSITORY", "")
    number = pr0.get("number", event.get("number"))
    event_head = (pr0.get("head") or {}).get("sha", "")
    if type(number) is not int or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo or ""):
        return ["event payload lacks repository/PR number; cannot read live PR state"]
    if not HEX40.fullmatch(event_head):
        return ["event payload lacks the PR head sha; cannot tell which head this run decides"]
    url = f"{os.environ.get('GITHUB_API_URL', 'https://api.github.com').rstrip('/')}/repos/{repo}/pulls/{number}"
    try:
        state = _read_live(get, url, repo)
        head, base, body = state[:3]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return [f"cannot read live PR state from the GitHub API ({exc.__class__.__name__}); failing closed, re-run when the API is reachable"]
    if head != event_head:
        return [f"stale run: this event is for head {event_head[:12]} but the PR head is now {head[:12]}; "
                "the run for the new head decides (a result for an old head is never reused)"]
    problem = _base_problem(state, repo)
    if problem:
        return [problem]
    try:
        subprocess.run(["git", "fetch", "--no-tags", "-q", remote, f"refs/heads/{TRUSTED_BASE_REF}"],
                       capture_output=True, text=True, check=True, timeout=180)
        trusted_tip = _git("rev-parse", "FETCH_HEAD")
    except (subprocess.SubprocessError, OSError):
        return [f"cannot fetch {TRUSTED_BASE_REF} from {remote}; failing closed"]
    if fetch_head:
        try:
            subprocess.run(["git", "fetch", "--no-tags", "-q", remote, f"+refs/pull/{number}/head"],
                           capture_output=True, text=True, check=True, timeout=180)
            if _git("rev-parse", "FETCH_HEAD") != head:
                return [f"PR head moved while checking (API {head[:12]}); re-run the check"]
        except (subprocess.SubprocessError, OSError):
            return [f"cannot fetch live PR head {head[:12]}; failing closed"]
    live_event = {"repository": {"full_name": repo},
                  "pull_request": {"number": number, "body": body, "head": {"sha": head}, "base": {"sha": trusted_tip}}}
    errors = check(live_event, lambda n, rh: load_offbranch_receipt(remote, n, rh))
    if errors:
        return errors
    try:
        final = _read_live(get, url, repo)
        if final != state:
            return ["PR head, body or base changed while the check ran; re-run (the run for the new state decides)"]
        problem = _base_problem(final, repo)
        if problem:
            return [problem]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return [f"cannot re-read live PR state ({exc.__class__.__name__}); failing closed"]
    return []


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_EVENT_PATH", "")
    if not path:
        print("check-review-disposition: no event payload (GITHUB_EVENT_PATH)", file=sys.stderr)
        return 2
    with open(path, encoding="utf-8") as fh:
        event = json.load(fh)
    errors = evaluate(event)
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
