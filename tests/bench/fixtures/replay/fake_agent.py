"""Fake agent for the replay tests: fixes src/m.py for the arms named in --fix-arms, prints one result event."""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="")
    ap.add_argument("--fix-arms", default="")
    ap.add_argument("--cost", type=float, default=0.0)
    ap.add_argument("--commit", action="store_true", help="commit the fix, like a real agent")
    ap.add_argument("--sleep", type=float, default=0.0)
    ap.add_argument("--list-to", help="write the clone's file listing to this file")
    ap.add_argument("--count-log", help="append one line per launch")
    a, _ = ap.parse_known_args()
    if a.count_log:
        with open(a.count_log, "a", encoding="utf-8") as f:
            f.write(a.arm + "\n")
    if a.sleep:
        time.sleep(a.sleep)
    if a.list_to:
        names = []
        for dirpath, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d != ".git"]
            names += [os.path.join(dirpath, x) for x in files]
        Path(a.list_to).write_text("\n".join(sorted(names)), encoding="utf-8")
    if a.arm in a.fix_arms.split(","):
        p = Path("src/m.py")
        p.write_text(p.read_text(encoding="utf-8").replace("a - b", "a + b"), encoding="utf-8")
        if a.commit:
            subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "fix"],
                           check=True, capture_output=True)
    print(json.dumps({"type": "result", "total_cost_usd": a.cost, "num_turns": 1, "result": "done",
                      "modelUsage": {"fake": {"inputTokens": 10, "outputTokens": 5, "cacheReadInputTokens": 0,
                                              "cacheCreationInputTokens": 0}}}))


if __name__ == "__main__":
    main()
