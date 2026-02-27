import os
import sys
import threading
from datetime import datetime

# TrayManager: robust Windows tray using native Shell_NotifyIcon (pywin32) when available.
# Falls back to pystray if pywin32 isn't installed.

class TrayManager:
    def __init__(self, root=None, title='ControllerCommander', tooltip=None, icon_path=None, debug_log_path='tray_debug.log', app_name=None):
        """
        Args:
            root: Tk root window.
            title: Tray icon name/title (main.py uses 'title').
            tooltip: Tooltip text shown on hover (defaults to title).
            icon_path: Optional .ico/.png path. If missing, a small default icon is generated for native backend.
            debug_log_path: Path to write tray debug logs.
            app_name: Back-compat alias for older code; if provided and title not set, used as title.
        """
        if (title is None or title == '') and app_name:
            title = app_name
        self.root = root
        self.app_name = title or 'App'
        self.tooltip = tooltip or self.app_name
        self.icon_path = icon_path
        self.debug_log_path = debug_log_path or 'tray_debug.log'
        self._icon_thread = None
        self._running = False
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._mode = None  # 'native' | 'pystray' | 'none'
        self._native_notify = None

        self._log('TrayManager initialized')
    def _log(self, msg: str):
        try:
            with open(self.debug_log_path, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] {msg}\n")
        except Exception:
            pass

    # -------- Public API used by main.py ----------
    def bind_close_to_tray(self):
        if not self.root:
            return
        self._log("Binding WM_DELETE_WINDOW to hide_to_tray")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

    def start(self, wait_s: float = 2.0) -> bool:
        """Start tray in background. Returns True if tray backend signaled ready."""
        if self._running:
            self._log("start(): tray already running")
            return True

        self._stop.clear()
        self._ready.clear()

        self._log(f"start(): requested (wait_s={wait_s})")

        # Prefer native Windows tray because pystray 'run_detached' can succeed but still show no icon.
        if sys.platform.startswith("win"):
            ok = self._start_native_windows(wait_s=wait_s)
            if ok:
                return True
            self._log("start(): native Windows tray failed or unavailable; falling back to pystray")

        ok = self._start_pystray(wait_s=wait_s)
        if ok:
            return True

        self._mode = "none"
        self._log("start(): tray failed in all modes")
        return False

    def hide_to_tray(self):
        """Hide the window only if tray is ready; otherwise close normally (never 'vanish')."""
        self._log("hide_to_tray() requested")
        ok = self.start(wait_s=1.5)
        if not ok:
            self._log("hide_to_tray(): tray not ready; destroying root (normal close)")
            try:
                if self.root:
                    self.root.destroy()
            except Exception as e:
                self._log(f"root.destroy failed: {type(e).__name__}: {e}")
            return

        try:
            if self.root:
                self.root.withdraw()
            self._log("hide_to_tray(): window withdrawn")
        except Exception as e:
            self._log(f"hide_to_tray(): withdraw failed: {type(e).__name__}: {e}")

    def show_window(self):
        if not self.root:
            return
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.after(10, self.root.focus_force)
        except Exception:
            pass

    def stop(self):
        self._log("stop(): requested")
        self._stop.set()

    def notify_once(self, title="Tray running", message="ControllerCommander is running in the tray."):
        try:
            if self._mode == "native" and hasattr(self, "_native_notify"):
                self._native_notify(title, message)
                self._log("notify_once(): native notify sent")
                return
        except Exception as e:
            self._log(f"notify_once(): native notify failed: {type(e).__name__}: {e}")

        try:
            if self._mode == "pystray" and getattr(self, "_pystray_icon", None) is not None:
                self._pystray_icon.notify(message, title=title)
                self._log("notify_once(): pystray notify sent")
        except Exception as e:
            self._log(f"notify_once(): pystray notify failed: {type(e).__name__}: {e}")

    # -------- Native Windows tray (pywin32) ----------
    def _start_native_windows(self, wait_s: float) -> bool:
        try:
            import win32con
            import win32gui
            import win32api
        except Exception as e:
            self._log(f"native: pywin32 not available: {type(e).__name__}: {e}")
            return False

        def _thread():
            try:
                self._mode = "native"
                self._running = True
                self._log("native: thread started")

                # Write a tiny cyan .ico
                ico_path = os.path.abspath("tray_icon.ico")
                try:
                    from PIL import Image, ImageDraw
                    img = Image.new("RGBA", (64, 64), (0, 200, 255, 255))
                    d = ImageDraw.Draw(img)
                    try:
                        d.rounded_rectangle((8, 8, 56, 56), radius=10, outline=(255, 255, 255, 255), width=4)
                    except Exception:
                        d.rectangle((8, 8, 56, 56), outline=(255, 255, 255, 255), width=4)
                    img.save(ico_path, format="ICO")
                    self._log(f"native: icon written {ico_path}")
                except Exception as e:
                    self._log(f"native: icon write failed: {type(e).__name__}: {e}")
                    ico_path = None

                class_name = "ControllerCommanderTrayWindow"
                WM_TRAY = win32con.WM_USER + 20

                def wndproc(hwnd, msg, wparam, lparam):
                    if msg == WM_TRAY:
                        if lparam in (win32con.WM_LBUTTONUP, win32con.WM_LBUTTONDBLCLK):
                            self._log("native: click -> show")
                            self.show_window()
                        elif lparam == win32con.WM_RBUTTONUP:
                            self._log("native: right click -> menu")
                            menu = win32gui.CreatePopupMenu()
                            win32gui.AppendMenu(menu, win32con.MF_STRING, 1023, "Show")
                            win32gui.AppendMenu(menu, win32con.MF_STRING, 1024, "Exit")
                            pos = win32gui.GetCursorPos()
                            win32gui.SetForegroundWindow(hwnd)
                            win32gui.TrackPopupMenu(
                                menu,
                                win32con.TPM_LEFTALIGN | win32con.TPM_RIGHTBUTTON,
                                pos[0],
                                pos[1],
                                0,
                                hwnd,
                                None,
                            )
                            win32gui.PostMessage(hwnd, win32con.WM_NULL, 0, 0)
                        return 0

                    if msg == win32con.WM_COMMAND:
                        cmd = win32gui.LOWORD(wparam)
                        if cmd == 1023:
                            self._log("native: menu show")
                            self.show_window()
                        elif cmd == 1024:
                            self._log("native: menu exit")
                            try:
                                if self.root:
                                    self.root.after(0, self.root.destroy)
                            except Exception:
                                pass
                            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                        return 0

                    if msg == win32con.WM_DESTROY:
                        self._log("native: WM_DESTROY")
                        try:
                            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (hwnd, 0))
                        except Exception:
                            pass
                        win32gui.PostQuitMessage(0)
                        return 0

                    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

                wc = win32gui.WNDCLASS()
                wc.hInstance = win32api.GetModuleHandle(None)
                wc.lpszClassName = class_name
                wc.lpfnWndProc = wndproc

                try:
                    win32gui.RegisterClass(wc)
                except Exception:
                    pass

                hwnd = win32gui.CreateWindow(
                    class_name,
                    self.app_name,
                    0,
                    0,
                    0,
                    win32con.CW_USEDEFAULT,
                    win32con.CW_USEDEFAULT,
                    0,
                    0,
                    wc.hInstance,
                    None,
                )

                # Load icon handle
                hicon = None
                try:
                    if ico_path and os.path.exists(ico_path):
                        hicon = win32gui.LoadImage(
                            wc.hInstance,
                            ico_path,
                            win32con.IMAGE_ICON,
                            0,
                            0,
                            win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE,
                        )
                except Exception as e:
                    self._log(f"native: LoadImage failed: {type(e).__name__}: {e}")

                if not hicon:
                    hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

                flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
                nid = (hwnd, 0, flags, WM_TRAY, hicon, self.tooltip)
                win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
                self._log("native: Shell_NotifyIcon NIM_ADD done")
                self._ready.set()

                def _native_notify(title, msg):
                    try:
                        nflags = win32gui.NIF_INFO
                        nid_info = (hwnd, 0, nflags, WM_TRAY, hicon, self.tooltip, msg, 200, title)
                        win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid_info)
                    except Exception as e:
                        self._log(f"native: notify failed: {type(e).__name__}: {e}")

                self._native_notify = _native_notify

                while not self._stop.is_set():
                    win32gui.PumpWaitingMessages()
                    win32api.Sleep(50)

                self._log("native: stop set, closing")
                try:
                    win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (hwnd, 0))
                except Exception:
                    pass
                try:
                    win32gui.DestroyWindow(hwnd)
                except Exception:
                    pass

            except Exception as e:
                self._log(f"native: fatal error: {type(e).__name__}: {e}")
            finally:
                self._running = False
                self._ready.set()

        self._icon_thread = threading.Thread(target=_thread, daemon=True)
        self._icon_thread.start()
        ok = self._ready.wait(timeout=max(0.2, float(wait_s)))
        self._log(f"native: ready wait done ok={ok}")
        return ok

    # -------- pystray fallback ----------
    def _start_pystray(self, wait_s: float) -> bool:
        try:
            import pystray
            from PIL import Image, ImageDraw
        except Exception as e:
            self._log(f"pystray: not available: {type(e).__name__}: {e}")
            return False

        def _run():
            try:
                self._mode = "pystray"
                self._running = True
                self._log("pystray: thread started")
                img = Image.new("RGBA", (64, 64), (0, 200, 255, 255))
                d = ImageDraw.Draw(img)
                try:
                    d.rounded_rectangle((8, 8, 56, 56), radius=10, outline=(255, 255, 255, 255), width=4)
                except Exception:
                    d.rectangle((8, 8, 56, 56), outline=(255, 255, 255, 255), width=4)

                menu = pystray.Menu(
                    pystray.MenuItem("Show", lambda icon, item: self.show_window()),
                    pystray.MenuItem("Exit", lambda icon, item: self._exit_from_tray()),
                )
                icon = pystray.Icon(self.app_name, img, self.tooltip, menu)
                self._pystray_icon = icon

                def _setup(i):
                    try:
                        i.visible = True
                    except Exception:
                        pass
                    self._ready.set()

                self._log("pystray: run_detached invoked")
                icon.run_detached(setup=_setup)
                ok = self._ready.wait(timeout=max(0.2, float(wait_s)))
                self._log(f"pystray: ready wait ok={ok}")
            except Exception as e:
                self._log(f"pystray: fatal error: {type(e).__name__}: {e}")
            finally:
                self._running = False
                self._ready.set()

        self._icon_thread = threading.Thread(target=_run, daemon=True)
        self._icon_thread.start()
        ok = self._ready.wait(timeout=max(0.2, float(wait_s)))
        self._log(f"start(): pystray ok={ok}")
        return ok

    def _exit_from_tray(self):
        self._log("exit requested from tray")
        try:
            if self.root:
                self.root.after(0, self.root.destroy)
        except Exception:
            pass
        self.stop()