import os
import sys
import tkinter as tk

from action_registry import ActionRegistry
from plugin_loader import load_plugins
from macro_engine import MacroEngine
from ui import AppUI

from profile_manager import ProfileManager
from controller_manager import ControllerManager
from logger import AppLogger

from tray import TrayManager
from startup_manager import StartupManager


_SINGLE_INSTANCE_LOCK = None


def _acquire_single_instance_lock(app_id="MacroCommander"):
    """Return (ok, reason) and hold a process-wide lock when ok=True."""
    global _SINGLE_INSTANCE_LOCK

    if _SINGLE_INSTANCE_LOCK is not None:
        return True, "already-held"

    if os.name == "nt":
        try:
            import ctypes
            import ctypes.wintypes

            kernel32 = ctypes.windll.kernel32
            # ERROR_ALREADY_EXISTS = 183
            ERROR_ALREADY_EXISTS = 183
            mutex_name = f"Global\\{app_id}"

            handle = kernel32.CreateMutexW(None, False, ctypes.wintypes.LPCWSTR(mutex_name))
            if not handle:
                return False, "CreateMutexW-failed"

            last_error = kernel32.GetLastError()
            if last_error == ERROR_ALREADY_EXISTS:
                kernel32.CloseHandle(handle)
                return False, "already-running"

            _SINGLE_INSTANCE_LOCK = handle
            return True, "ok"
        except Exception:
            # Fall through to file-lock fallback below.
            pass

    lock_path = os.path.join(_ensure_dir(os.path.expanduser("~")), f".{app_id}.lock")
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        _SINGLE_INSTANCE_LOCK = (fd, lock_path)
        return True, "ok"
    except FileExistsError:
        return False, "already-running"
    except Exception:
        return True, "lock-unavailable"


def _release_single_instance_lock():
    global _SINGLE_INSTANCE_LOCK
    lock = _SINGLE_INSTANCE_LOCK
    _SINGLE_INSTANCE_LOCK = None
    if lock is None:
        return

    if os.name == "nt" and isinstance(lock, int):
        try:
            import ctypes

            ctypes.windll.kernel32.CloseHandle(lock)
        except Exception:
            pass
        return

    if isinstance(lock, tuple) and len(lock) == 2:
        fd, lock_path = lock
        try:
            os.close(fd)
        except Exception:
            pass
        try:
            os.unlink(lock_path)
        except Exception:
            pass


def _notify_already_running(root):
    try:
        from tkinter import messagebox

        messagebox.showinfo("Macro Commander", "Macro Commander is already running.")
    except Exception:
        pass


def register_builtin_actions(registry: ActionRegistry):
    import subprocess
    import webbrowser
    import shlex

    def parse_args(arg_text):
        raw = str(arg_text or "").strip()
        if not raw:
            return []
        try:
            return shlex.split(raw, posix=False)
        except Exception:
            return [raw]

    def run_exe(params):
        path = str(params.get("path", "")).strip()
        args = parse_args(params.get("args", ""))
        if not path:
            return False, "Missing EXE path"
        try:
            subprocess.Popen([path, *args], shell=False)
            return True, f"Ran EXE: {path} {' '.join(args)}".strip()
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def run_bat(params):
        path = str(params.get("path", "")).strip()
        args = parse_args(params.get("args", ""))
        if not path:
            return False, "Missing BAT/CMD path"
        try:
            subprocess.Popen(["cmd.exe", "/c", path, *args], shell=False)
            return True, f"Ran BAT/CMD: {path} {' '.join(args)}".strip()
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def run_py(params):
        path = str(params.get("path", "")).strip()
        args = parse_args(params.get("args", ""))
        if not path:
            return False, "Missing PY path"
        try:
            subprocess.Popen([sys.executable, path, *args], shell=False)
            return True, f"Ran PY: {path} {' '.join(args)}".strip()
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def run_ps1(params):
        path = str(params.get("path", "")).strip()
        args = parse_args(params.get("args", ""))
        if not path:
            return False, "Missing PS1 path"
        try:
            subprocess.Popen(["powershell", "-ExecutionPolicy", "Bypass", "-File", path, *args], shell=False)
            return True, f"Ran PS1: {path} {' '.join(args)}".strip()
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
            },
            "args": {
                "type": "string",
                "label": "Arguments",
                "required": False,
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
            },
            "args": {
                "type": "string",
                "label": "Arguments",
                "required": False,
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
            },
            "args": {
                "type": "string",
                "label": "Arguments",
                "required": False,
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
            },
            "args": {
                "type": "string",
                "label": "Arguments",
                "required": False,
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


def _get_runtime_dirs():
    """Return directories for writable data and bundled resources."""
    source_dir = os.path.dirname(os.path.abspath(__file__))
    exe_dir = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else source_dir
    bundle_dir = getattr(sys, "_MEIPASS", source_dir)
    return {
        "source_dir": source_dir,
        "exe_dir": exe_dir,
        "bundle_dir": bundle_dir,
    }


def _iter_plugin_dirs(runtime_dirs):
    """Yield unique plugin directories in priority order."""
    candidates = [
        os.path.join(runtime_dirs["exe_dir"], "plugins"),
        os.path.join(runtime_dirs["bundle_dir"], "plugins"),
        os.path.join(runtime_dirs["source_dir"], "plugins"),
    ]

    seen = set()
    for candidate in candidates:
        normalized = os.path.normcase(os.path.normpath(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        yield candidate


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



def _load_startup_options(profile_manager):
    fn = getattr(profile_manager, "load_app_settings", None)
    if callable(fn):
        try:
            data = fn()
            if isinstance(data, dict):
                return {
                    "start_with_windows": bool(data.get("start_with_windows", False)),
                    "start_minimized": bool(data.get("start_minimized", False)),
                }
        except Exception:
            pass
    return {"start_with_windows": False, "start_minimized": False}


def _save_startup_options(profile_manager, options):
    fn = getattr(profile_manager, "save_app_settings", None)
    if callable(fn):
        try:
            fn(options)
            return True
        except Exception:
            return False
    return False


def main():
    ok, _ = _acquire_single_instance_lock(app_id="MacroCommander")
    if not ok:
        root = tk.Tk()
        root.withdraw()
        _notify_already_running(root)
        root.destroy()
        return

    root = tk.Tk()
    logger = AppLogger()

    runtime_dirs = _get_runtime_dirs()
    base_dir = runtime_dirs["exe_dir"]

    profile_dir = _ensure_dir(os.path.join(base_dir, "profiles"))
    profile_manager = ProfileManager(profile_dir)
    macros = _load_macros(profile_manager, logger)

    startup_options = _load_startup_options(profile_manager)
    should_start_minimized = bool(startup_options.get("start_minimized", False))

    # Avoid the startup flash when "Start Minimized" is enabled.
    # Withdrawing before UI/tray initialization prevents the first map-to-screen.
    if should_start_minimized:
        root.withdraw()

    startup_target = sys.executable if getattr(sys, "frozen", False) else __file__
    startup_manager = StartupManager(app_name="ControllerMacroRunner", script_path=startup_target)

    startup_options["start_with_windows"] = bool(startup_manager.is_enabled())
    _save_startup_options(profile_manager, startup_options)

    registry = ActionRegistry()
    register_builtin_actions(registry)

    loaded_plugin_dir = None
    for plugins_dir in _iter_plugin_dirs(runtime_dirs):
        if os.path.isdir(plugins_dir):
            load_plugins(registry, plugins_dir=plugins_dir, logger=logger)
            loaded_plugin_dir = plugins_dir
            break

    if logger and loaded_plugin_dir is None:
        logger.log("Plugins: no plugin directory found in runtime paths")

    macro_engine = MacroEngine(
        profile_manager=profile_manager,
        macros=macros,
        registry=registry,
        logger=logger
    )

    controller_manager = ControllerManager(macro_engine)
    _start_controller_manager(controller_manager, logger)

    def on_toggle_start_with_windows(enabled):
        ok, msg = startup_manager.set_enabled(bool(enabled))
        if ok:
            startup_options["start_with_windows"] = bool(enabled)
            _save_startup_options(profile_manager, startup_options)
            if logger:
                logger.log(msg)
        return ok, msg

    def on_toggle_start_minimized(enabled):
        startup_options["start_minimized"] = bool(enabled)
        ok = _save_startup_options(profile_manager, startup_options)
        if not ok:
            return False, "Failed to save startup setting."
        if logger:
            logger.log(f"Start Minimized set to {bool(enabled)}")
        return True, "Saved"

    tray_debug_log = os.path.join(base_dir, "tray_debug.log")
    tray = TrayManager(
        root,
        title="Controller Macro Runner",
        tooltip="Controller Macro Runner",
        debug_log_path=tray_debug_log
    )

    def on_exit_app():
        try:
            tray.stop()
        except Exception:
            pass
        root.after(0, root.destroy)

    app_ui = AppUI(
        root,
        macro_engine,
        controller_manager,
        registry=registry,
        logger=logger,
        startup_options=startup_options,
        on_toggle_start_with_windows=on_toggle_start_with_windows,
        on_toggle_start_minimized=on_toggle_start_minimized,
        on_exit_app=on_exit_app,
    )

    tray.bind_close_to_tray()

    # Tray is initialized in the background.
    def initialize_tray():
        try:
            ok = tray.start(wait_s=4.0)
        except Exception:
            ok = False

        if not ok:
            logger.log(f"Tray failed to start. See debug log: {tray_debug_log}")

        if should_start_minimized:
            if not ok:
                # If tray startup fails, show the app so it doesn't appear to vanish.
                root.deiconify()
                root.lift()
                root.focus_force()
        else:
            root.deiconify()
            root.lift()
            root.focus_force()

    root.after(200, initialize_tray)

    try:
        root.mainloop()
    finally:
        _release_single_instance_lock()


if __name__ == "__main__":
    main()
