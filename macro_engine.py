import time
import threading
from execution_engine import execute_macro


class MacroEngine:
    def __init__(self, profile_manager, macros, registry, logger=None):
        self.profile_manager = profile_manager
        self.macros = macros or []
        self.registry = registry
        self.logger = logger

        self.controller_state = {}
        self.on_macro_fired = None

        self._normalize_all()

    def set_on_macro_fired(self, callback):
        self.on_macro_fired = callback

    def _normalize_combo(self, combo):
        return tuple(sorted(combo))

    def _legacy_to_action_step(self, action_type: str, target: str):
        at = str(action_type).upper().strip()
        tgt = str(target).strip()

        if at == "URL":
            return {"kind": "run", "action_id": "open.url", "params": {"url": tgt}}

        mapping = {
            "EXE": ("file.exe", "path"),
            "BAT": ("file.bat", "path"),
            "PY":  ("file.py", "path"),
            "PS1": ("file.ps1", "path"),
        }
        if at in mapping:
            aid, key = mapping[at]
            return {"kind": "run", "action_id": aid, "params": {key: tgt}}

        # unknown legacy
        return {"kind": "run", "action_id": "file.exe", "params": {"path": tgt}}

    def _normalize_steps(self, macro):
        steps = macro.get("steps", None)

        # Back-compat: build steps from legacy fields if missing
        if not isinstance(steps, list) or len(steps) == 0:
            legacy_type = str(macro.get("action_type", "")).upper().strip()
            legacy_target = str(macro.get("target", "")).strip()
            if legacy_type:
                macro["steps"] = [self._legacy_to_action_step(legacy_type, legacy_target)]
            else:
                macro["steps"] = []
            steps = macro["steps"]

        cleaned = []
        for s in steps:
            if not isinstance(s, dict):
                if self.logger:
                    self.logger.log(f"Skipping invalid step entry of type {type(s).__name__}")
                continue

            kind = str(s.get("kind", "run")).lower().strip()

            if kind == "wait":
                try:
                    secs = float(s.get("seconds", 0.0))
                    if secs < 0:
                        secs = 0.0
                except Exception:
                    secs = 0.0
                cleaned.append({"kind": "wait", "seconds": secs})
                continue

            # RUN: accept either new or legacy keys
            action_id = str(s.get("action_id", "")).strip()
            params = s.get("params", {})
            if not isinstance(params, dict):
                params = {}

            if not action_id:
                # legacy -> new
                at = s.get("action_type", macro.get("action_type", "EXE"))
                tgt = s.get("target", macro.get("target", ""))
                cleaned.append(self._legacy_to_action_step(at, tgt))
            else:
                cleaned.append({"kind": "run", "action_id": action_id, "params": dict(params)})

        macro["steps"] = cleaned

        # Best-effort legacy sync for older displays
        first_run = next((x for x in cleaned if x.get("kind") == "run"), None)
        if first_run:
            aid = first_run.get("action_id", "")
            p = first_run.get("params", {}) or {}
            if aid == "open.url":
                macro["action_type"] = "URL"
                macro["target"] = p.get("url", "")
            elif aid == "file.exe":
                macro["action_type"] = "EXE"
                macro["target"] = p.get("path", "")
            elif aid == "file.bat":
                macro["action_type"] = "BAT"
                macro["target"] = p.get("path", "")
            elif aid == "file.py":
                macro["action_type"] = "PY"
                macro["target"] = p.get("path", "")
            elif aid == "file.ps1":
                macro["action_type"] = "PS1"
                macro["target"] = p.get("path", "")
            else:
                macro["action_type"] = "EXE"
                macro["target"] = ""
        else:
            macro["action_type"] = "EXE"
            macro["target"] = ""

    def _normalize_all(self):
        used = set()
        next_id = 1

        for m in self.macros:
            if "id" not in m or not isinstance(m["id"], int) or m["id"] in used:
                while next_id in used:
                    next_id += 1
                m["id"] = next_id
            used.add(m["id"])

            m["combo"] = list(self._normalize_combo(m.get("combo", [])))
            m["active"] = bool(m.get("active", True))

            try:
                m["hold_seconds"] = float(m.get("hold_seconds", 0.0))
                if m["hold_seconds"] < 0:
                    m["hold_seconds"] = 0.0
            except Exception:
                m["hold_seconds"] = 0.0

            self._normalize_steps(m)

        self.save()

    def _next_id(self):
        return (max([m["id"] for m in self.macros], default=0) + 1)

    def save(self):
        self.profile_manager.save_profile(self.macros)

    # -------- CRUD --------

    def add_macro(self, combo, hold_seconds, active=True, steps=None):
        combo_t = self._normalize_combo(combo)

        try:
            hold_seconds = float(hold_seconds)
            if hold_seconds < 0:
                hold_seconds = 0.0
        except Exception:
            hold_seconds = 0.0

        macro = {
            "id": self._next_id(),
            "combo": list(combo_t),
            "active": bool(active),
            "hold_seconds": hold_seconds,
            "steps": steps if isinstance(steps, list) else [],
        }
        self._normalize_steps(macro)

        # Basic duplicate check (combo+hold+steps)
        def freeze(value):
            if isinstance(value, dict):
                return tuple(sorted((str(k), freeze(v)) for k, v in value.items()))
            if isinstance(value, (list, tuple, set)):
                return tuple(freeze(v) for v in value)
            return value

        def sig(m):
            s = []
            for st in m.get("steps", []):
                if st.get("kind") == "wait":
                    s.append(("wait", float(st.get("seconds", 0.0))))
                else:
                    s.append(("run", st.get("action_id", ""), freeze(st.get("params", {}) or {})))
            return (tuple(self._normalize_combo(m.get("combo", []))),
                    float(m.get("hold_seconds", 0.0)),
                    tuple(s))

        new_sig = sig(macro)
        for existing in self.macros:
            if sig(existing) == new_sig:
                return None

        self.macros.append(macro)
        self.save()
        return macro["id"]

    def remove_macro_by_id(self, macro_id):
        self.macros = [m for m in self.macros if m.get("id") != macro_id]
        self.save()

    def set_macro_active(self, macro_id, active):
        for m in self.macros:
            if m.get("id") == macro_id:
                m["active"] = bool(active)
                break
        self.save()

    def get_macro_by_id(self, macro_id):
        for m in self.macros:
            if m.get("id") == macro_id:
                return m
        return None

    def update_macro(self, macro_id, combo, hold_seconds, active, steps):
        m = self.get_macro_by_id(macro_id)
        if not m:
            return False

        combo_t = self._normalize_combo(combo)

        try:
            hold_s = float(hold_seconds)
            if hold_s < 0:
                hold_s = 0.0
        except Exception:
            hold_s = 0.0

        candidate = {
            "id": macro_id,
            "combo": list(combo_t),
            "active": bool(active),
            "hold_seconds": hold_s,
            "steps": steps if isinstance(steps, list) else [],
        }
        self._normalize_steps(candidate)

        def freeze(value):
            if isinstance(value, dict):
                return tuple(sorted((str(k), freeze(v)) for k, v in value.items()))
            if isinstance(value, (list, tuple, set)):
                return tuple(freeze(v) for v in value)
            return value

        def sig(m2):
            s = []
            for st in m2.get("steps", []):
                if st.get("kind") == "wait":
                    s.append(("wait", float(st.get("seconds", 0.0))))
                else:
                    s.append(("run", st.get("action_id", ""), freeze(st.get("params", {}) or {})))
            return (tuple(self._normalize_combo(m2.get("combo", []))),
                    float(m2.get("hold_seconds", 0.0)),
                    tuple(s))

        cand_sig = sig(candidate)
        for other in self.macros:
            if other.get("id") == macro_id:
                continue
            if sig(other) == cand_sig:
                return False

        m["combo"] = candidate["combo"]
        m["active"] = candidate["active"]
        m["hold_seconds"] = candidate["hold_seconds"]
        m["steps"] = candidate["steps"]
        self._normalize_steps(m)

        self.save()
        return True

    # -------- Runtime --------

    def _fire(self, controller_id, macro):
        combo_str = " + ".join(macro.get("combo", []))
        hs = float(macro.get("hold_seconds", 0.0))

        def step_log(line):
            if self.logger:
                self.logger.log(f"c{controller_id} | {combo_str} | {line}")

        def worker():
            if self.logger:
                self.logger.log(f"FIRE c{controller_id} | {combo_str} | hold={hs} | steps={len(macro.get('steps', []) or [])}")

            ok, msg = execute_macro(macro, registry=self.registry, step_logger=step_log)

            if self.logger:
                self.logger.log(f"DONE c{controller_id} | {combo_str} | ok={ok} | {msg}")

            cb = self.on_macro_fired
            if cb:
                try:
                    cb(controller_id, macro, ok, msg)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def check_combo(self, controller_id, pressed_buttons):
        combo = self._normalize_combo(pressed_buttons)
        now = time.time()

        if controller_id not in self.controller_state:
            self.controller_state[controller_id] = {
                "current_combo": (),
                "start_time": 0.0,
                "triggered_ids": set(),
            }

        st = self.controller_state[controller_id]

        if combo != st["current_combo"]:
            st["current_combo"] = combo
            st["start_time"] = now
            st["triggered_ids"].clear()

        if not combo:
            return

        held_time = now - st["start_time"]

        for m in self.macros:
            if not m.get("active", True):
                continue
            if self._normalize_combo(m.get("combo", [])) != combo:
                continue

            mid = m.get("id")
            if mid in st["triggered_ids"]:
                continue

            hs = float(m.get("hold_seconds", 0.0))

            if hs <= 0.0:
                self._fire(controller_id, m)
                st["triggered_ids"].add(mid)
            else:
                if held_time >= hs:
                    self._fire(controller_id, m)
                    st["triggered_ids"].add(mid)
