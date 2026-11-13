"""Fake judge for the replay tests: logs one line per call, prints `Score: N`."""
import argparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", type=int, default=7)
    ap.add_argument("--log")
    ap.add_argument("--diff-file")
    ap.add_argument("--diff-log", help="append 1 when the diff the judge received holds the fix, else 0")
    a, _ = ap.parse_known_args()
    if a.log:
        with open(a.log, "a", encoding="utf-8") as f:
            f.write("judged\n")
    if a.diff_log and a.diff_file:
        with open(a.diff_log, "a", encoding="utf-8") as f:
            f.write(f"{int('+    return a + b' in open(a.diff_file, encoding='utf-8').read())}\n")
    print(f"Score: {a.score}")


if __name__ == "__main__":
    main()
