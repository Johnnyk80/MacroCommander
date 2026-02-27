import os
import tkinter as tk

from action_registry import ActionRegistry
from plugin_loader import load_plugins
from macro_engine import MacroEngine
from ui import AppUI

from profile_manager import ProfileManager
from controller_manager import ControllerManager
from logger import AppLogger

from tray import TrayManager


def register_builtin_actions(registry: ActionRegistry):
    import subprocess
    import webbrowser

    def run_exe(params):
        path = str(params.get("path", "")).strip()
        if not path:
            return False, "Missing EXE path"
        try:
            subprocess.Popen([path], shell=False)
            return True, f"Ran EXE: {path}"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def run_bat(params):
        path = str(params.get("path", "")).strip()
        if not path:
            return False, "Missing BAT/CMD path"
        try:
            subprocess.Popen(["cmd.exe", "/c", path], shell=False)
            return True, f"Ran BAT/CMD: {path}"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def run_py(params):
        path = str(params.get("path", "")).strip()
        if not path:
            return False, "Missing PY path"
        try:
            subprocess.Popen(["python", path], shell=False)
            return True, f"Ran PY: {path}"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def run_ps1(params):
        path = str(params.get("path", "")).strip()
        if not path:
            return False, "Missing PS1 path"
        try:
            subprocess.Popen(["powershell", "-ExecutionPolicy", "Bypass", "-File", path], shell=False)
            return True, f"Ran PS1: {path}"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def open_url(params):
        url = str(params.get("url", "")).strip()
        if not url:
            return False, "Missing URL"
        try:
            webbrowser.open(url)
            return True, f"Opened URL: {url}"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    registry.register_action(
        action_id="file.exe",
        name="Run EXE",
        description="Launch an executable (.exe).",
        schema={
            "path": {
                "type": "file",
                "label": "Executable",
                "required": True,
                "filetypes": [("Executable (*.exe)", "*.exe"), ("All files", "*.*")]
            }
        },
        run=run_exe
    )

    registry.register_action(
        action_id="file.bat",
        name="Run BAT/CMD",
        description="Run a batch script (.bat/.cmd).",
        schema={
            "path": {
                "type": "file",
                "label": "Script",
                "required": True,
                "filetypes": [("Batch (*.bat;*.cmd)", "*.bat;*.cmd"), ("All files", "*.*")]
            }
        },
        run=run_bat
    )

    registry.register_action(
        action_id="file.py",
        name="Run Python Script",
        description="Run a Python script using 'python script.py'.",
        schema={
            "path": {
                "type": "file",
                "label": "Script",
                "required": True,
                "filetypes": [("Python (*.py)", "*.py"), ("All files", "*.*")]
            }
        },
        run=run_py
    )

    registry.register_action(
        action_id="file.ps1",
        name="Run PowerShell Script",
        description="Run a PowerShell script (.ps1).",
        schema={
            "path": {
                "type": "file",
                "label": "Script",
                "required": True,
                "filetypes": [("PowerShell (*.ps1)", "*.ps1"), ("All files", "*.*")]
            }
        },
        run=run_ps1
    )

    registry.register_action(
        action_id="open.url",
        name="Open URL",
        description="Open a URL in the default browser.",
        schema={"url": {"type": "string", "label": "URL", "required": True}},
        run=open_url
    )


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def _load_macros(profile_manager, logger):
    for name in ("load_profile_or_default", "load_or_default", "load", "load_profile", "load_default_profile", "get_macros"):
        fn = getattr(profile_manager, name, None)
        if callable(fn):
            try:
                macros = fn()
                return macros if macros is not None else []
            except Exception:
                pass
    return []


def _start_controller_manager(cm, logger):
    for method_name in ("start", "start_polling", "run", "begin", "start_thread"):
        fn = getattr(cm, method_name, None)
        if callable(fn):
            try:
                fn()
                if logger:
                    logger.log(f"ControllerManager: started via {method_name}()")
                return
            except Exception as e:
                if logger:
                    logger.log(f"ControllerManager: {method_name}() failed: {type(e).__name__}: {e}")


def main():
    root = tk.Tk()
    logger = AppLogger()

    base_dir = os.path.dirname(os.path.abspath(__file__))

    profile_dir = _ensure_dir(os.path.join(base_dir, "profiles"))
    profile_manager = ProfileManager(profile_dir)
    macros = _load_macros(profile_manager, logger)

    registry = ActionRegistry()
    register_builtin_actions(registry)

    plugins_dir = os.path.join(base_dir, "plugins")
    load_plugins(registry, plugins_dir=plugins_dir, logger=logger)

    macro_engine = MacroEngine(
        profile_manager=profile_manager,
        macros=macros,
        registry=registry,
        logger=logger
    )

    controller_manager = ControllerManager(macro_engine)
    _start_controller_manager(controller_manager, logger)

    app_ui = AppUI(
        root,
        macro_engine,
        controller_manager,
        registry=registry,
        logger=logger
    )

    tray_debug_log = os.path.join(base_dir, "tray_debug.log")
    tray = TrayManager(
        root,
        title="Controller Macro Runner",
        tooltip="Controller Macro Runner",
        debug_log_path=tray_debug_log
    )
    tray.bind_close_to_tray()

    # ✅ START VISIBLE:
    # App starts on screen. Tray is initialized in the background.
    # Closing the window (X) will still hide to tray via WM_DELETE binding.
    def initialize_tray():
        try:
            ok = tray.start(wait_s=4.0)
        except Exception:
            ok = False

        if not ok:
            logger.log(f"Tray failed to start. See debug log: {tray_debug_log}")

        # Keep the main window visible on startup regardless.
        root.deiconify()
        root.lift()
        root.focus_force()

    root.after(200, initialize_tray)

    root.mainloop()


if __name__ == "__main__":
    main()
