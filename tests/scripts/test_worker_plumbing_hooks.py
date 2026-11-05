import json
from test_fleet_hooks import HOOKS, run_hook

def test_lead_stop_record_goes_to_the_parent_run(tmp_path):
    main, lsd = tmp_path / "main" / ".superlite", tmp_path / "wt" / ".superlite"
    for d in (main, lsd):
        d.mkdir(parents=True)
    env = {"SUPERLITE_FLEET_WORKER": "W2", "SUPERLITE_FLEET_AGENT": "lead", "SUPERLITE_FLEET_ROLE": "lead", "SUPERLITE_STATE_DIR": str(lsd)}
    stdin = json.dumps({"session_id": "s1", "transcript_path": "/t/l.jsonl", "last_assistant_message": "Status: DONE"})
    run_hook("capture-worker-stop", stdin, {**env, "SUPERLITE_FLEET_PARENT_DIR": str(main)}, lsd.parent)
    rec = json.loads((main / "metrics.jsonl").read_text().splitlines()[-1])
    assert (rec["agent_id"], rec["type"], rec["last"]) == ("W2", "fleet:lead", "Status: DONE") and not (lsd / "metrics.jsonl").exists()
    run_hook("capture-worker-stop", stdin, {**env, "SUPERLITE_FLEET_PARENT_DIR": str(tmp_path / "gone")}, lsd.parent)
    assert (lsd / "metrics.jsonl").exists() and not (tmp_path / "gone").exists()

def test_worker_prompts_are_never_human_replies(tmp_path):
    sd = tmp_path / ".superlite"; sd.mkdir(); (sd / "orchestrator.json").write_text('{"mode": "human", "approved": false}')
    stdin = json.dumps({"session_id": "s1", "prompt": "go ahead and ship it"})
    run_hook("record-human-reply", stdin, {"SUPERLITE_FLEET_WORKER": "W2", "SUPERLITE_FLEET_ROLE": "lead", "SUPERLITE_STATE_DIR": str(sd)}, tmp_path)
    assert not (sd / "human-replies.jsonl").exists()
    run_hook("record-human-reply", stdin, {"SUPERLITE_STATE_DIR": str(sd)}, tmp_path)
    assert json.loads((sd / "human-replies.jsonl").read_text())["approves"] is True

def test_permission_dialogs_are_denied_in_every_fleet_pane(tmp_path):
    req = json.dumps({"session_id": "s1", "hook_event_name": "PermissionRequest", "tool_name": "Bash", "tool_input": {"command": "rm -rf x"}})
    for role in ("lead", "implementer", "final-reviewer"):
        d = json.loads(run_hook("deny-worker-permission", req, {"SUPERLITE_FLEET_WORKER": "W2", "SUPERLITE_FLEET_ROLE": role}, tmp_path).stdout)
        dec = d["hookSpecificOutput"]
        assert (dec["hookEventName"], dec["decision"]["behavior"]) == ("PermissionRequest", "deny") and "No human watches this pane" in dec["decision"]["message"]
    assert run_hook("deny-worker-permission", req, {}, tmp_path).stdout == ""
    cfg = json.loads((HOOKS / "hooks.json").read_text())
    assert [h["command"] for e in cfg["hooks"]["PermissionRequest"] for h in e["hooks"]] == ['bash "${CLAUDE_PLUGIN_ROOT}/hooks/deny-worker-permission"']
