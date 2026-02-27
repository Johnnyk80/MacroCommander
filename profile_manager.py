import os
import json


class ProfileManager:
    def __init__(self, profile_dir):
        self.profile_dir = profile_dir
        self.default_profile_path = os.path.join(profile_dir, "default.json")
        self.app_settings_path = os.path.join(profile_dir, "app_settings.json")

    def load_default_profile(self):
        if not os.path.exists(self.default_profile_path):
            self.save_profile([])
            return []

        with open(self.default_profile_path, "r") as f:
            data = json.load(f)

        return data.get("macros", [])

    def save_profile(self, macros):
        data = {
            "profile_name": "default",
            "macros": macros
        }

        with open(self.default_profile_path, "w") as f:
            json.dump(data, f, indent=4)


    def load_app_settings(self):
        defaults = {"start_with_windows": False, "start_minimized": False}
        if not os.path.exists(self.app_settings_path):
            return dict(defaults)

        try:
            with open(self.app_settings_path, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return dict(defaults)
            out = dict(defaults)
            out["start_with_windows"] = bool(data.get("start_with_windows", False))
            out["start_minimized"] = bool(data.get("start_minimized", False))
            return out
        except Exception:
            return dict(defaults)

    def save_app_settings(self, settings):
        payload = {
            "start_with_windows": bool((settings or {}).get("start_with_windows", False)),
            "start_minimized": bool((settings or {}).get("start_minimized", False)),
        }

        with open(self.app_settings_path, "w") as f:
            json.dump(payload, f, indent=4)
