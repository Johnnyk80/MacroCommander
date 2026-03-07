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
    """XInput-only controller manager with logical queue-style slot compaction."""

    def __init__(self, macro_engine, max_controllers=4, poll_hz=125):
        self.macro_engine = macro_engine
        self.max_controllers = int(max_controllers)
        self.sleep_s = 1.0 / float(poll_hz)

        self.connected = {i: False for i in range(self.max_controllers)}
        self.latest = {i: None for i in range(self.max_controllers)}
        self.pressed = {i: tuple() for i in range(self.max_controllers)}

        # Logical<->physical mapping (queue behavior)
        self._logical_to_physical = {i: None for i in range(self.max_controllers)}
        self._physical_to_logical = {}

        self.listen_armed = False
        self.listen_callback = None
        self._listen_controller = None
        self._listen_seen_any_press = False
        self._listen_union = set()

        self._vib_tokens = {i: 0 for i in range(self.max_controllers)}
        self._vib_lock = threading.Lock()

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
                if self.connected.get(cid) and combo:
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

    def _get_state(self, controller_id):
        if XINPUT is None:
            return None
        state = XINPUT_STATE()
        res = XINPUT.XInputGetState(controller_id, ctypes.byref(state))
        if res != 0:
            return None
        return state.Gamepad

    def _buttons_to_names(self, wbuttons):
        out = []
        for mask, name in BUTTON_MAP.items():
            if wbuttons & mask:
                out.append(name)
        out.sort()
        return tuple(out)

    def _set_vibration(self, physical_id, left_speed, right_speed):
        if XINPUT is None:
            return 1
        left = int(max(0, min(65535, left_speed)))
        right = int(max(0, min(65535, right_speed)))
        vib = XINPUT_VIBRATION(left, right)
        return XINPUT.XInputSetState(physical_id, ctypes.byref(vib))

    def vibrate(self, controller_id, left=32000, right=32000, duration_ms=120):
        cid = int(controller_id)
        if cid < 0 or cid >= self.max_controllers:
            return
        if not self.connected.get(cid, False):
            return

        physical_id = self._logical_to_physical.get(cid)
        if physical_id is None:
            return

        with self._vib_lock:
            self._vib_tokens[cid] += 1
            token = self._vib_tokens[cid]

        def _worker():
            self._set_vibration(physical_id, left, right)
            end_t = time.time() + (max(0, int(duration_ms)) / 1000.0)
            while time.time() < end_t:
                with self._vib_lock:
                    if self._vib_tokens[cid] != token:
                        break
                time.sleep(0.01)
            with self._vib_lock:
                still_current = (self._vib_tokens[cid] == token)
            if still_current:
                self._set_vibration(physical_id, 0, 0)

        threading.Thread(target=_worker, daemon=True).start()

    def _compact_mappings(self, active_physical_ids):
        # Remove disconnected physical ids from current queue
        keep = []
        for logical in range(self.max_controllers):
            pid = self._logical_to_physical.get(logical)
            if pid in active_physical_ids:
                keep.append(pid)

        # Append newly connected physical ids in physical index order
        for pid in active_physical_ids:
            if pid not in keep:
                keep.append(pid)

        self._logical_to_physical = {i: None for i in range(self.max_controllers)}
        self._physical_to_logical = {}
        for logical, pid in enumerate(keep[:self.max_controllers]):
            self._logical_to_physical[logical] = pid
            self._physical_to_logical[pid] = logical

    def run(self):
        while True:
            physical_states = {}
            for physical_id in range(self.max_controllers):
                gp = self._get_state(physical_id)
                if gp is not None:
                    physical_states[physical_id] = gp

            self._compact_mappings(sorted(physical_states.keys()))

            for logical_id in range(self.max_controllers):
                physical_id = self._logical_to_physical.get(logical_id)
                if physical_id is None or physical_id not in physical_states:
                    was_connected = self.connected.get(logical_id, False)
                    self.connected[logical_id] = False
                    self.latest[logical_id] = None
                    if self.pressed.get(logical_id, tuple()):
                        self.pressed[logical_id] = tuple()
                    if was_connected and self.macro_engine is not None:
                        self.macro_engine.check_combo(logical_id, tuple())
                    if self.listen_armed and self._listen_controller == logical_id:
                        self.cancel_listen()
                    continue

                gp = physical_states[physical_id]
                self.connected[logical_id] = True
                self.latest[logical_id] = gp

                pressed_names = self._buttons_to_names(gp.wButtons)
                if pressed_names != self.pressed.get(logical_id, tuple()):
                    self.pressed[logical_id] = pressed_names

                # Always tick combo state so hold timers can complete even when
                # the button set remains unchanged for multiple polling frames.
                if self.macro_engine is not None:
                    self.macro_engine.check_combo(logical_id, pressed_names)

            if self.listen_armed:
                self._listen_tick()

            time.sleep(self.sleep_s)

    def get_connected_ids(self):
        return [cid for cid in range(self.max_controllers) if self.connected.get(cid)]

    def get_backend(self, _controller_id):
        return "xinput"

    def get_device_label(self, controller_id):
        physical = self._logical_to_physical.get(int(controller_id))
        if physical is None:
            return f"XInput Controller {int(controller_id)}"
        return f"XInput Controller {physical}"

    def get_gamepad(self, controller_id):
        return self.latest.get(controller_id)

    def get_pressed_combo(self, controller_id):
        return self.pressed.get(controller_id, tuple())


def _cc__cm_start(self):
    if getattr(self, "_cc_thread", None) and getattr(self._cc_thread, "is_alive", lambda: False)():
        return
    t = threading.Thread(target=self.run, daemon=True)
    self._cc_thread = t
    t.start()


if not hasattr(ControllerManager, "start"):
    ControllerManager.start = _cc__cm_start
if not hasattr(ControllerManager, "start_polling"):
    ControllerManager.start_polling = _cc__cm_start
if not hasattr(ControllerManager, "start_thread"):
    ControllerManager.start_thread = _cc__cm_start
