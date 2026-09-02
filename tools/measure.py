#!/usr/bin/env python3
"""Measurement harness for BUILD_PLAN.md section 4 — the two human-read numbers.

Runs `greenwash --commit <sha> --json` across the newest N commits in a real
repository that touch BOTH src/main and src/test in the same commit, and tallies:

  * the INCONCLUSIVE_COMPILE rate (compile-wall measurement, section 9) — this
    decides whether step 14's fallback is promoted to a real verdict;
  * every commit that comes back blocking (FIX_IS_IN_THE_TESTS or
    CONFIG_WEAKENED). On a corpus of honest, human-authored commits each of
    these is a candidate NFR-6 false positive and must be reviewed by hand.

The harness picks nothing and concludes nothing on its own. A human chooses the
repository, runs this, and reads the flagged commits.

Results are cached per-sha in --out and the run is resumable: kill it at any
point and rerun with the same --out to continue.

stdlib only; nothing here is imported by greenwash/.

Examples
--------
    # what would be measured, without running anything
    python3 tools/measure.py ~/Documents/greenwash-corpus/commons-lang \
        --n 25 --list-only

    # smoke run, then read the histogram
    python3 tools/measure.py ~/Documents/greenwash-corpus/commons-lang --n 25

    # full run in the background, resumable
    nohup python3 tools/measure.py ~/Documents/greenwash-corpus/commons-lang \
        --n 200 --out commons-lang.json > commons-lang.log 2>&1 &
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# A commit is in-scope only if it changes something under both trees. Kept broad
# (not .../java) so config-under-src and resource changes still count.
MAIN_PREFIXES = ("src/main/",)
TEST_PREFIXES = ("src/test/",)

BLOCKING = {"FIX_IS_IN_THE_TESTS", "CONFIG_WEAKENED"}
NOT_ANALYSABLE = {"ERROR", "TIMEOUT"}


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    )
    return proc.stdout


def commit_summary(repo: Path, sha: str) -> str:
    return git(repo, "show", "-s", "--format=%h %ad %s", "--date=short", sha).strip()


def _touches_both(repo: Path, sha: str) -> bool:
    files = [f for f in git(
        repo, "show", "--no-renames", "--pretty=format:", "--name-only", sha
    ).splitlines() if f]
    has_main = any(f.startswith(p) for f in files for p in MAIN_PREFIXES)
    has_test = any(f.startswith(p) for f in files for p in TEST_PREFIXES)
    return has_main and has_test


def select_commits(repo: Path, n: int, since: str | None) -> list[str]:
    """Newest `n` non-merge first-parent commits that touch both trees."""
    args = ["log", "--first-parent", "--no-merges", "--format=%H"]
    if since:
        args.append(f"--since={since}")
    args += ["--", "src/main", "src/test"]
    picked: list[str] = []
    for sha in git(repo, *args).splitlines():
        if sha and _touches_both(repo, sha):
            picked.append(sha)
            if len(picked) >= n:
                break
    return picked


def _subject(detail: dict) -> str:
    if "goal" in detail:
        return str(detail["goal"])
    if "classname" in detail and "name" in detail:
        return f"{detail['classname']}.{detail['name']}"
    if "path" in detail:
        return str(detail["path"])
    return str(detail.get("reason", ""))


def run_one(gw: str, repo: Path, sha: str, timeout: int) -> dict:
    t0 = time.time()
    rec: dict = {"sha": sha, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        proc = subprocess.run(
            [gw, "--commit", sha, "--json"],
            cwd=str(repo), capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        rec.update(verdict="TIMEOUT", duration_s=timeout)
        return rec

    rec["duration_s"] = round(time.time() - t0, 1)
    rec["exit_code"] = proc.returncode
    stderr_tail = proc.stderr.strip()[-800:]
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        # NFR-4 fail-open path, or greenwash crashed before printing JSON.
        rec.update(verdict="ERROR", stderr_tail=stderr_tail)
        return rec

    rec["verdict"] = payload["headline_verdict"]
    rec["blocking"] = payload["blocking"]
    rec["findings"] = [
        {"verdict": f["verdict"], "module": f["module"], "subject": _subject(f["detail"])}
        for f in payload["findings"]
    ]
    if stderr_tail:
        rec["stderr_tail"] = stderr_tail
    return rec


def _find_greenwash(repo: Path, override: str | None) -> str:
    if override:
        return override
    sibling = repo.parent / ".venv" / "bin" / "greenwash"
    if sibling.exists():
        return str(sibling)
    found = shutil.which("greenwash")
    if found:
        return found
    sys.exit("greenwash not found on PATH or in <repo>/../.venv; pass --greenwash PATH")


def load_cache(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {"repo": None, "results": {}}


def save_cache(path: Path, cache: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(cache, indent=2, sort_keys=True))
    tmp.replace(path)


def report(cache: dict, shas: list[str]) -> None:
    rows = [cache["results"][s] for s in shas if s in cache["results"]]
    hist: dict[str, int] = {}
    for r in rows:
        hist[r["verdict"]] = hist.get(r["verdict"], 0) + 1
    total = len(rows)
    analysable = sum(c for k, c in hist.items() if k not in NOT_ANALYSABLE)
    inconclusive_compile = hist.get("INCONCLUSIVE_COMPILE", 0)

    print("\n=== verdict histogram ===")
    for k in sorted(hist, key=lambda k: (-hist[k], k)):
        print(f"  {hist[k]:4d}  {k}")
    print(f"\ntotal: {total}   analysable (excl {'/'.join(sorted(NOT_ANALYSABLE))}): {analysable}")
    if analysable:
        pct = inconclusive_compile / analysable
        print(f"INCONCLUSIVE_COMPILE rate: {inconclusive_compile}/{analysable} = {pct:.1%}   (section 9 measurement)")

    blocking = [r for r in rows if r.get("verdict") in BLOCKING]
    print(f"\n=== blocking verdicts — review each by hand (NFR-6): {len(blocking)} ===")
    for r in blocking:
        print(f"  {r['sha']}  {r['verdict']}   {r.get('duration_s', '?')}s")
        for f in r.get("findings", []):
            print(f"      {f['verdict']}  module={f['module']}  {f['subject']}")
    if analysable:
        rate = len(blocking) / analysable
        print(f"\nblocking rate: {len(blocking)}/{analysable} = {rate:.1%}   (NFR-6 budget: <= 2%, honest corpus)")

    errs = [r for r in rows if r.get("verdict") in NOT_ANALYSABLE]
    if errs:
        print(f"\n=== {len(errs)} ERROR/TIMEOUT (excluded from rates) ===")
        for r in errs:
            print(f"  {r['sha']}  {r['verdict']}")
            if r.get("stderr_tail"):
                print(f"      {r['stderr_tail'].splitlines()[-1]}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", type=Path, help="path to the target repository clone")
    ap.add_argument("--n", type=int, default=200, help="number of in-scope commits to measure (default 200)")
    ap.add_argument("--since", default=None, help="git --since filter, e.g. '3 years ago' (keeps old commits buildable)")
    ap.add_argument("--out", type=Path, default=Path("measure-results.json"), help="per-sha result cache (resumable)")
    ap.add_argument("--greenwash", default=None, help="path to the greenwash CLI (default: <repo>/../.venv/bin/greenwash, then PATH)")
    ap.add_argument("--commit-timeout", type=int, default=3600, help="hard wall-clock cap per commit in seconds (default 3600)")
    ap.add_argument("--jobs", type=int, default=1, help="commits to measure concurrently, each greenwash run isolated in its own worktree (default 1)")
    ap.add_argument("--list-only", action="store_true", help="print the selected commits and exit")
    args = ap.parse_args(argv)

    repo = args.repo.expanduser().resolve()
    if not (repo / ".git").exists():
        sys.exit(f"not a git repository: {repo}")

    shas = select_commits(repo, args.n, args.since)
    if not shas:
        sys.exit("no commits touch both src/main and src/test in range")

    if args.list_only:
        for s in shas:
            print(commit_summary(repo, s))
        print(f"\n{len(shas)} commits", file=sys.stderr)
        return 0

    gw = _find_greenwash(repo, args.greenwash)
    cache = load_cache(args.out)
    cache["repo"] = str(repo)
    cache.setdefault("results", {})

    pending = [s for s in shas if s not in cache["results"]]
    done = len(shas) - len(pending)
    jobs = max(1, args.jobs)
    print(f"greenwash: {gw}")
    print(f"{len(shas)} commits selected  |  {done} cached  |  {len(pending)} to run  |  jobs={jobs}")
    if jobs > 1:
        print(f"note: each job runs its own build; set -DforkCount to ~{max(1, 8 // jobs)} in "
              f".greenwash.toml so {jobs} concurrent builds do not oversubscribe the machine")

    lock = threading.Lock()
    durations: list[float] = []
    n_pending = len(pending)
    state = {"finished": 0}

    def work(sha: str) -> None:
        try:
            rec = run_one(gw, repo, sha, args.commit_timeout)
        except Exception as exc:  # keep one bad commit from killing the run
            rec = {"sha": sha, "verdict": "ERROR", "stderr_tail": repr(exc)}
        with lock:
            cache["results"][sha] = rec
            save_cache(args.out, cache)
            state["finished"] += 1
            i = state["finished"]
            if isinstance(rec.get("duration_s"), (int, float)):
                durations.append(float(rec["duration_s"]))
            eta = ""
            if durations:
                avg = sum(durations) / len(durations)
                secs = avg * (n_pending - i) / jobs
                eta = f"   eta ~{secs / 3600:.1f}h" if secs >= 3600 else f"   eta ~{secs / 60:.0f}m"
            print(f"[{i}/{n_pending}] {rec['verdict']:<24} {rec.get('duration_s', '?')}s   "
                  f"{sha[:12]}{eta}", flush=True)

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        for _ in ex.map(work, pending):
            pass

    report(cache, shas)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
