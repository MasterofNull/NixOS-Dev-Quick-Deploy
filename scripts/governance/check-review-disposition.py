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

Receipt: fetched at run time from the append-only `review-receipts` branch
(receipts/pr<N>-<head12>.json, schema 2, published by `aq-review-receipt publish`),
so issuing it never changes the PR head. It must bind this repo, this PR,
Reviewed-head-sha and that commit's tree, name a non-author reviewer and agree with
the body (reviewer, author, disposition). A head that differs from Reviewed-head-sha
is accepted only under the merge-only rule below. Receipt missing or malformed, or a
branch that cannot be fetched, fails. Schema 1 receipts committed in the PR are no
longer accepted (the migration path was removed when `aq-land` began issuing
off-branch receipts); a `Review-Receipt:` body line is ignored.

Trust boundary: the workflow runs on `pull_request_target`, so the workflow definition and
this checker come from the base branch (main), never from the PR. The PR contributes only the
event payload and git objects fetched as data (`refs/pull/<N>/head`); nothing from it is
executed. A PR that edits this file, the workflow or check-pr-body-format.py is judged by main's
copy. The change that introduces this arrangement is itself judged by the previous workflow on
main (see the bootstrap note in its evidence file). Residual risk: a change to the checker is
effective only after it merges, and anyone who can push to main or edit branch protection can
still change the rules.

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
first-parent chain head..Reviewed-head-sha is a merge whose second parent is
an ancestor of the tip of origin's `refs/heads/main`, fetched by this run and never
taken from the API's base sha, and whose tree equals the clean automatic result of
`git merge-tree --write-tree <first-parent> <second-parent>` (needs git >= 2.38; the
runner image's git is checked at run time and the check fails closed if it is older).
Conflicted or hand-edited merges and ordinary commits need a new review.

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
RECEIPT_BRANCH = "review-receipts"
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


def merge_only_update(rhead, head, base):
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


def check(event, receipt_loader):
    """Return the error list. receipt_loader(pr_number, rhead) -> (receipt|None, error|None)."""
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
        ok, detail = merge_only_update(rhead, head, base) if head else (False, "no PR head")
        if ok:
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
    r, rerr = (None, None)
    if HEX40.fullmatch(rhead or ""):
        if type(pr_number) is not int or not repo:
            errors.append("event lacks repository/PR number; cannot locate off-branch receipt")
        else:
            r, rerr = receipt_loader(pr_number, rhead)
    if r is not None:
        errors += check_offbranch_receipt(r, repo, pr_number, rhead, reviewer, author, disp)
    elif rerr:
        errors.append(rerr)
    else:
        errors.append(f"missing receipt: none on {RECEIPT_BRANCH} for PR {pr_number} head {(rhead or '')[:12]}")
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
