import os
import sys


class StartupManager:
    """Manage per-user Windows auto-start via HKCU\\...\\Run."""

    def __init__(self, app_name: str, script_path: str):
        self.app_name = str(app_name).strip() or "ControllerMacroRunner"
        self.script_path = os.path.abspath(script_path)

    @property
    def supported(self) -> bool:
        return os.name == "nt"

    def _build_command(self) -> str:
        python_exe = os.path.abspath(sys.executable)
        return f'"{python_exe}" "{self.script_path}"'

    def is_enabled(self) -> bool:
        if not self.supported:
            return False

        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, self.app_name)
            return str(value).strip() == self._build_command()
        except Exception:
            return False

    def set_enabled(self, enabled: bool) -> tuple[bool, str]:
        if not self.supported:
            return False, "Start with Windows is only supported on Windows."

        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                if enabled:
                    winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, self._build_command())
                    return True, "Enabled Start with Windows."
                try:
                    winreg.DeleteValue(key, self.app_name)
                except FileNotFoundError:
                    pass
                return True, "Disabled Start with Windows."
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"
