import ctypes
import time
import threading
from ctypes import wintypes


def _load_xinput():
    for dll_name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
        try:
            return ctypes.WinDLL(dll_name)
        except Exception:
            continue
    return None


XINPUT = _load_xinput()


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", wintypes.WORD),
        ("bLeftTrigger", wintypes.BYTE),
        ("bRightTrigger", wintypes.BYTE),
        ("sThumbLX", wintypes.SHORT),
        ("sThumbLY", wintypes.SHORT),
        ("sThumbRX", wintypes.SHORT),
        ("sThumbRY", wintypes.SHORT),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", wintypes.DWORD),
        ("Gamepad", XINPUT_GAMEPAD),
    ]


class XINPUT_VIBRATION(ctypes.Structure):
    _fields_ = [
        ("wLeftMotorSpeed", wintypes.WORD),
        ("wRightMotorSpeed", wintypes.WORD),
    ]


if XINPUT is not None:
    XINPUT.XInputGetState.argtypes = [wintypes.DWORD, ctypes.POINTER(XINPUT_STATE)]
    XINPUT.XInputGetState.restype = wintypes.DWORD

    # XInputSetState returns DWORD error code (0 = SUCCESS)
    XINPUT.XInputSetState.argtypes = [wintypes.DWORD, ctypes.POINTER(XINPUT_VIBRATION)]
    XINPUT.XInputSetState.restype = wintypes.DWORD


BUTTON_MAP = {
    0x1000: "A",
    0x2000: "B",
    0x4000: "X",
    0x8000: "Y",
    0x0100: "LB",
    0x0200: "RB",
    0x0020: "Back",
    0x0010: "Start",
    0x0040: "LS",
    0x0080: "RS",
    0x0001: "DPad Up",
    0x0002: "DPad Down",
    0x0004: "DPad Left",
    0x0008: "DPad Right",
}


class ControllerManager:
    """
    Polls up to 4 XInput controllers (XInput limitation).
    Stores latest states for UI, and sends combos to macro engine.
    Supports Listen Mode: press buttons (any order) + release -> captures FULL union combo
    from FIRST controller that presses.

    Also provides vibration feedback via XInputSetState.
    """

    def __init__(self, macro_engine, max_controllers=4, poll_hz=100):
        self.macro_engine = macro_engine
        self.max_controllers = int(max_controllers)
        self.sleep_s = 1.0 / float(poll_hz)

        self.connected = {i: False for i in range(self.max_controllers)}
        self.latest = {i: None for i in range(self.max_controllers)}
        self.pressed = {i: tuple() for i in range(self.max_controllers)}

        # Listen mode state
        self.listen_armed = False
        self.listen_callback = None
        self._listen_controller = None
        self._listen_seen_any_press = False
        self._listen_union = set()

        # Vibration cancel tokens per controller
        self._vib_tokens = {i: 0 for i in range(self.max_controllers)}
        self._vib_lock = threading.Lock()

    # ---------------- Listen Mode ----------------

    def arm_listen(self, callback):
        self.listen_armed = True
        self.listen_callback = callback
        self._listen_controller = None
        self._listen_seen_any_press = False
        self._listen_union = set()

    def cancel_listen(self):
        self.listen_armed = False
        self.listen_callback = None
        self._listen_controller = None
        self._listen_seen_any_press = False
        self._listen_union = set()

    def _listen_tick(self):
        if self._listen_controller is None:
            for cid in range(self.max_controllers):
                combo = self.pressed.get(cid, tuple())
                if self.connected.get(cid) and len(combo) > 0:
                    self._listen_controller = cid
                    self._listen_seen_any_press = True
                    self._listen_union.update(combo)
                    break
            return

        combo = self.pressed.get(self._listen_controller, tuple())

        if combo:
            self._listen_seen_any_press = True
            self._listen_union.update(combo)
            return

        if self._listen_seen_any_press and self._listen_union:
            cb = self.listen_callback
            cid = self._listen_controller
            captured = tuple(sorted(self._listen_union))

            self.cancel_listen()

            if cb:
                cb(cid, captured)

    # ---------------- XInput polling ----------------

    def _get_state(self, controller_id):
        if XINPUT is None:
            return None
        state = XINPUT_STATE()
        res = XINPUT.XInputGetState(controller_id, ctypes.byref(state))
        if res != 0:
            return None
        return state.Gamepad

    def _buttons_to_names(self, wButtons):
        out = []
        for mask, name in BUTTON_MAP.items():
            if wButtons & mask:
                out.append(name)
        out.sort()
        return tuple(out)

    # ---------------- Vibration ----------------

    def _set_vibration(self, controller_id, left_speed, right_speed):
        if XINPUT is None:
            return 1
        left = int(max(0, min(65535, left_speed)))
        right = int(max(0, min(65535, right_speed)))
        vib = XINPUT_VIBRATION(left, right)
        return XINPUT.XInputSetState(controller_id, ctypes.byref(vib))

    def vibrate(self, controller_id, left=32000, right=32000, duration_ms=120):
        """
        Non-blocking vibration. Cancels any previous vibration on the same controller.
        """
        cid = int(controller_id)
        if cid < 0 or cid >= self.max_controllers:
            return

        # If not connected, do nothing
        if not self.connected.get(cid, False):
            return

        with self._vib_lock:
            self._vib_tokens[cid] += 1
            token = self._vib_tokens[cid]

        def _worker():
            # Start
            self._set_vibration(cid, left, right)
            end_t = time.time() + (max(0, int(duration_ms)) / 1000.0)

            # Allow cancellation during the vibration
            while time.time() < end_t:
                with self._vib_lock:
                    if self._vib_tokens[cid] != token:
                        break
                time.sleep(0.01)

            # Stop only if still current
            with self._vib_lock:
                still_current = (self._vib_tokens[cid] == token)
            if still_current:
                self._set_vibration(cid, 0, 0)

        threading.Thread(target=_worker, daemon=True).start()

    # ---------------- Main Loop ----------------

    def run(self):
        while True:
            for cid in range(self.max_controllers):
                gp = self._get_state(cid)

                if gp is None:
                    self.connected[cid] = False
                    self.latest[cid] = None
                    self.pressed[cid] = tuple()

                    if self.listen_armed and self._listen_controller == cid:
                        self.cancel_listen()
                    continue

                self.connected[cid] = True
                self.latest[cid] = gp

                pressed_names = self._buttons_to_names(gp.wButtons)
                self.pressed[cid] = pressed_names

                if self.macro_engine is not None:
                    self.macro_engine.check_combo(cid, pressed_names)

            if self.listen_armed:
                self._listen_tick()

            time.sleep(self.sleep_s)

    # ---------------- UI helpers ----------------

    def get_connected_ids(self):
        return [cid for cid in range(self.max_controllers) if self.connected.get(cid)]

    def get_gamepad(self, controller_id):
        return self.latest.get(controller_id)

    def get_pressed_combo(self, controller_id):
        return self.pressed.get(controller_id, tuple())


# ---- Patch: non-blocking start() for UI friendliness ----
def _cc__cm_start(self):
    import threading
    if getattr(self, "_cc_thread", None) and getattr(self._cc_thread, "is_alive", lambda: False)():
        return
    t = threading.Thread(target=self.run, daemon=True)
    self._cc_thread = t
    t.start()

# Attach if missing
if not hasattr(ControllerManager, "start"):
    ControllerManager.start = _cc__cm_start
if not hasattr(ControllerManager, "start_polling"):
    ControllerManager.start_polling = _cc__cm_start
if not hasattr(ControllerManager, "start_thread"):
    ControllerManager.start_thread = _cc__cm_start
