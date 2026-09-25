#!/usr/bin/env python3
"""Claude Code hook entry point (CLAUDE.md section 9).

  hook.py post   PostToolUse on Write|Edit|MultiEdit. Runs `verify.py --hook` when the
                 edited file is under data/, sources/ or report/. Exit 2 feeds the
                 failures back to Claude.
  hook.py stop   Stop. Runs `verify.py --hook`; exit 2 blocks stopping. If the input has
                 stop_hook_active true, never blocks again: the open failures are left in
                 reports/verification_report.md and reported to the user.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

WATCHED = ("data/", "sources/", "report/")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        data = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        data = {}
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or Path(__file__).resolve().parents[1]).resolve()
    verify = [sys.executable, str(root / "tools" / "verify.py"), "--hook", "--root", str(root), "--quiet"]

    if event == "post":
        fp = (data.get("tool_input") or {}).get("file_path") or ""
        if not fp:
            return 0
        path = Path(fp)
        if not path.is_absolute():
            path = root / path
        try:
            rel = path.resolve().relative_to(root).as_posix()
        except ValueError:
            return 0
        if not rel.startswith(WATCHED):
            return 0
        extra = ["--files", str(path.resolve())] if rel.startswith("report/chapters/") and rel.endswith(".md") else []
        r = subprocess.run(verify + extra, capture_output=True, text=True, encoding="utf-8", env=env)
        if r.returncode == 2:
            sys.stderr.write(f"Verifier failed after editing {rel}. Fix these before continuing:\n{r.stderr}")
            return 2
        if r.returncode != 0:
            sys.stderr.write(f"Verifier error (exit {r.returncode}):\n{r.stderr}")
            return 1
        return 0

    if event == "stop":
        r = subprocess.run(verify, capture_output=True, text=True, encoding="utf-8", env=env)
        if r.returncode == 0:
            return 0
        if data.get("stop_hook_active"):
            msg = ("Verifier still failing after a retry. Open failures are listed in "
                   "reports/verification_report.md and need Hassan's attention.\n" + r.stderr[:3000])
            print(json.dumps({"systemMessage": msg}))
            return 0
        sys.stderr.write("Do not stop yet: the verifier is failing. Resolve these failures, "
                         "or explain to Hassan why they cannot be resolved now:\n" + r.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
