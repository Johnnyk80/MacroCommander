import os
import json


class ProfileManager:
    def __init__(self, profile_dir):
        self.profile_dir = profile_dir
        self.default_profile_path = os.path.join(profile_dir, "default.json")

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
