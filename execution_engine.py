import time


def execute_macro(macro: dict, registry, step_logger=None):
    """
    Executes macro steps using ActionRegistry.

    Step formats supported:
      New:
        {"kind":"run","action_id":"some.action","params":{...}}
        {"kind":"wait","seconds": 1.5}
      Legacy:
        {"kind":"run","action_type":"EXE|BAT|PY|PS1|URL","target":"..."}
        (auto-converted by macro_engine, but we keep fallback)
    """
    steps = macro.get("steps")
    if not isinstance(steps, list) or not steps:
        return False, "No steps"

    for idx, step in enumerate(steps, start=1):
        kind = str(step.get("kind", "run")).lower().strip()

        if kind == "wait":
            try:
                secs = float(step.get("seconds", 0.0))
                if secs < 0:
                    secs = 0.0
            except Exception:
                secs = 0.0

            if step_logger:
                step_logger(f"Step {idx}: WAIT {secs:g}s")

            time.sleep(secs)
            continue

        # RUN
        action_id = step.get("action_id", "")
        params = step.get("params", {})

        # legacy fallback
        if not action_id:
            at = str(step.get("action_type", "")).upper().strip()
            tgt = str(step.get("target", "")).strip()
            action_id = {
                "EXE": "file.exe",
                "BAT": "file.bat",
                "PY":  "file.py",
                "PS1": "file.ps1",
                "URL": "open.url",
            }.get(at, "")
            params = {"path": tgt} if action_id.startswith("file.") else {"url": tgt}

        if step_logger:
            step_logger(f"Step {idx}: RUN {action_id}")

        action = registry.get(action_id) if registry else None
        if not action:
            return False, f"Step {idx} failed: unknown action_id '{action_id}'"

        ok, msg = action.run(params or {})
        if step_logger:
            step_logger(f"Step {idx} result: ok={ok} | {msg}")

        if not ok:
            return False, f"Step {idx} failed: {msg}"

    return True, f"Executed {len(steps)} step(s)"
