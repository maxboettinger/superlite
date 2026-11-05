Q = {"questions": [{"question": "Keep the v1 API?", "header": "API", "options": [{"label": "Keep (Recommended)", "description": "no break"},
                                                                              {"label": "Drop", "description": "smaller"}], "multiSelect": False}]}
APPROVED = {"by": "AskUserQuestion", "time": "2026-11-05T10:00:00Z"}

def batch(bid, files, state="planned", **kw):
    return {"id": bid, "topic": "t", "issues": [int(bid[1:])], "files": list(files), "depends": [], "decisions": [], "state": state,
            "answers": {}, "lead": None, "agent": None, "worktree": None, "branch": None, "since": 0, "pr": None, "merged": False,
            "version": None, "reason": "", "ship_runs": 0, "questions": 0, **kw}
