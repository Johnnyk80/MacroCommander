import ctypes
import threading
import time
from ctypes import wintypes


def _optional_import(module_name):
    try:
        return __import__(module_name)
    except Exception:
        return None


PYGAME = _optional_import("pygame")
HID = _optional_import("hid")
INPUTS = _optional_import("inputs")


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

GENERIC_BUTTON_MAP = {
    0: "A",
    1: "B",
    2: "X",
    3: "Y",
    4: "LB",
    5: "RB",
    6: "Back",
    7: "Start",
    8: "LS",
    9: "RS",
}

INPUTS_BUTTON_MAP = {
    "BTN_SOUTH": "A",
    "BTN_A": "A",
    "BTN_EAST": "B",
    "BTN_B": "B",
    "BTN_WEST": "X",
    "BTN_X": "X",
    "BTN_NORTH": "Y",
    "BTN_Y": "Y",
    "BTN_TL": "LB",
    "BTN_TL2": "LB",
    "BTN_TR": "RB",
    "BTN_TR2": "RB",
    "BTN_SELECT": "Back",
    "BTN_MODE": "Back",
    "BTN_START": "Start",
    "BTN_THUMBL": "LS",
    "BTN_THUMBR": "RS",
    "BTN_DPAD_UP": "DPad Up",
    "BTN_DPAD_DOWN": "DPad Down",
    "BTN_DPAD_LEFT": "DPad Left",
    "BTN_DPAD_RIGHT": "DPad Right",
}


class GenericGamepadState:
    def __init__(self, lt=0, rt=0, lx=0, ly=0, rx=0, ry=0):
        self.bLeftTrigger = int(max(0, min(255, lt)))
        self.bRightTrigger = int(max(0, min(255, rt)))
        self.sThumbLX = int(max(-32768, min(32767, lx)))
        self.sThumbLY = int(max(-32768, min(32767, ly)))
        self.sThumbRX = int(max(-32768, min(32767, rx)))
        self.sThumbRY = int(max(-32768, min(32767, ry)))


class ControllerManager:
    def __init__(self, macro_engine, max_controllers=4, poll_hz=100):
        self.macro_engine = macro_engine
        self.max_controllers = int(max_controllers)
        self.sleep_s = 1.0 / float(poll_hz)

        self.connected = {}
        self.latest = {}
        self.pressed = {}
        self.names = {}

        self._known_ids = [self._xid(i) for i in range(self.max_controllers)]
        for cid in self._known_ids:
            self.connected[cid] = False
            self.latest[cid] = None
            self.pressed[cid] = tuple()
            self.names[cid] = cid

        self.listen_armed = False
        self.listen_callback = None
        self._listen_controller = None
        self._listen_seen_any_press = False
        self._listen_union = set()

        self._vib_tokens = {self._xid(i): 0 for i in range(self.max_controllers)}
        self._vib_lock = threading.Lock()

        self._inputs_lock = threading.Lock()
        self._inputs_axes = {}

        self._init_pygame()
        self._start_inputs_loop_if_available()

    def _xid(self, idx):
        return f"xinput:{int(idx)}"

    def _pid(self, idx):
        return f"pygame:{int(idx)}"

    def _iid(self, idx):
        return f"inputs:{int(idx)}"

    def _init_pygame(self):
        self._pygame_ok = False
        if PYGAME is None:
            return
        try:
            if not PYGAME.get_init():
                PYGAME.init()
            PYGAME.joystick.init()
            self._pygame_ok = True
        except Exception:
            self._pygame_ok = False

    def _start_inputs_loop_if_available(self):
        self._inputs_ok = False
        if INPUTS is None:
            return

        get_gamepad = getattr(INPUTS, "get_gamepad", None)
        if not callable(get_gamepad):
            return

        self._inputs_ok = True
        t = threading.Thread(target=self._inputs_global_loop, daemon=True)
        t.start()

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
            for cid in self.get_known_ids():
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

    def _get_xinput_state(self, idx):
        if XINPUT is None:
            return None
        state = XINPUT_STATE()
        res = XINPUT.XInputGetState(idx, ctypes.byref(state))
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

    def _normalize_axis(self, value):
        try:
            return int(max(-32768, min(32767, float(value) * 32767.0)))
        except Exception:
            return 0

    def _normalize_trigger(self, value):
        try:
            v = float(value)
        except Exception:
            return 0
        if v < 0:
            v = (v + 1.0) / 2.0
        return int(max(0, min(255, v * 255.0)))

    def _normalize_inputs_thumb(self, value):
        try:
            v = int(value)
        except Exception:
            v = 0

        if v > 32767:
            v = int((v / 65535.0) * 65535.0 - 32768.0)
        return int(max(-32768, min(32767, v)))

    def _normalize_inputs_trigger(self, value):
        try:
            v = int(value)
        except Exception:
            v = 0

        if v > 255:
            v = int((v / 1023.0) * 255.0) if v <= 1023 else int((v / 65535.0) * 255.0)
        return int(max(0, min(255, v)))

    def _poll_pygame(self):
        if not self._pygame_ok:
            return

        try:
            PYGAME.event.pump()
            count = PYGAME.joystick.get_count()
        except Exception:
            return

        seen = set()
        for idx in range(count):
            cid = self._pid(idx)
            seen.add(cid)
            if cid not in self._known_ids:
                self._known_ids.append(cid)

            try:
                joy = PYGAME.joystick.Joystick(idx)
                joy.init()
                self.connected[cid] = True
                self.names[cid] = f"{joy.get_name()} (pygame:{idx})"

                pressed = set()
                for b in range(int(joy.get_numbuttons())):
                    if joy.get_button(b):
                        pressed.add(GENERIC_BUTTON_MAP.get(b, f"Button {b}"))

                for h in range(int(joy.get_numhats())):
                    hx, hy = joy.get_hat(h)
                    if hy > 0:
                        pressed.add("DPad Up")
                    elif hy < 0:
                        pressed.add("DPad Down")
                    if hx < 0:
                        pressed.add("DPad Left")
                    elif hx > 0:
                        pressed.add("DPad Right")

                self.pressed[cid] = tuple(sorted(pressed))

                axis_count = int(joy.get_numaxes())
                axes = [joy.get_axis(a) for a in range(axis_count)]
                self.latest[cid] = GenericGamepadState(
                    lt=self._normalize_trigger(axes[4]) if axis_count > 4 else 0,
                    rt=self._normalize_trigger(axes[5]) if axis_count > 5 else 0,
                    lx=self._normalize_axis(axes[0]) if axis_count > 0 else 0,
                    ly=self._normalize_axis(axes[1]) if axis_count > 1 else 0,
                    rx=self._normalize_axis(axes[2]) if axis_count > 2 else 0,
                    ry=self._normalize_axis(axes[3]) if axis_count > 3 else 0,
                )
            except Exception:
                self.connected[cid] = False
                self.latest[cid] = None
                self.pressed[cid] = tuple()

        for cid in [x for x in self._known_ids if x.startswith("pygame:")]:
            if cid not in seen:
                self.connected[cid] = False
                self.latest[cid] = None
                self.pressed[cid] = tuple()

    def _inputs_global_loop(self):
        while True:
            try:
                events = INPUTS.get_gamepad()
            except Exception:
                time.sleep(0.25)
                continue

            with self._inputs_lock:
                for ev in events:
                    dev_name = str(getattr(getattr(ev, "device", None), "name", "") or "unknown")
                    cid = self._iid(0)
                    if cid not in self._known_ids:
                        self._known_ids.append(cid)
                    self.connected[cid] = True
                    self.names[cid] = f"{dev_name} (inputs:0)"

                    if cid not in self.pressed:
                        self.pressed[cid] = tuple()
                    if cid not in self._inputs_axes:
                        self._inputs_axes[cid] = {
                            "ABS_X": 0,
                            "ABS_Y": 0,
                            "ABS_RX": 0,
                            "ABS_RY": 0,
                            "ABS_Z": 0,
                            "ABS_RZ": 0,
                            "ABS_BRAKE": 0,
                            "ABS_GAS": 0,
                        }

                    pressed = set(self.pressed.get(cid, tuple()))
                    axis = self._inputs_axes[cid]
                    code = str(getattr(ev, "code", ""))
                    state = int(getattr(ev, "state", 0))

                    if code in INPUTS_BUTTON_MAP:
                        name = INPUTS_BUTTON_MAP[code]
                        if state:
                            pressed.add(name)
                        else:
                            pressed.discard(name)
                    elif code == "ABS_HAT0X":
                        pressed.discard("DPad Left")
                        pressed.discard("DPad Right")
                        if state < 0:
                            pressed.add("DPad Left")
                        elif state > 0:
                            pressed.add("DPad Right")
                    elif code == "ABS_HAT0Y":
                        pressed.discard("DPad Up")
                        pressed.discard("DPad Down")
                        if state < 0:
                            pressed.add("DPad Up")
                        elif state > 0:
                            pressed.add("DPad Down")
                    elif code in axis:
                        axis[code] = state

                    self.pressed[cid] = tuple(sorted(pressed))
                    self.latest[cid] = GenericGamepadState(
                        lt=self._normalize_inputs_trigger(axis.get("ABS_Z", 0) or axis.get("ABS_BRAKE", 0)),
                        rt=self._normalize_inputs_trigger(axis.get("ABS_RZ", 0) or axis.get("ABS_GAS", 0)),
                        lx=self._normalize_inputs_thumb(axis.get("ABS_X", 0)),
                        ly=self._normalize_inputs_thumb(axis.get("ABS_Y", 0)),
                        rx=self._normalize_inputs_thumb(axis.get("ABS_RX", 0)),
                        ry=self._normalize_inputs_thumb(axis.get("ABS_RY", 0)),
                    )

    def get_hid_gamepad_devices(self):
        if HID is None:
            return []
        out = []
        try:
            for dev in HID.enumerate():
                usage_page = int(dev.get("usage_page", -1))
                usage = int(dev.get("usage", -1))
                if usage_page == 0x01 and usage in (0x04, 0x05):
                    out.append(dev)
        except Exception:
            return []
        return out

    def _set_vibration(self, xinput_id, left_speed, right_speed):
        if XINPUT is None:
            return 1
        left = int(max(0, min(65535, left_speed)))
        right = int(max(0, min(65535, right_speed)))
        vib = XINPUT_VIBRATION(left, right)
        return XINPUT.XInputSetState(int(xinput_id), ctypes.byref(vib))

    def vibrate(self, controller_id, left=32000, right=32000, duration_ms=120):
        cid = str(controller_id)
        if not cid.startswith("xinput:"):
            return
        if not self.connected.get(cid, False):
            return

        xidx = int(cid.split(":", 1)[1])
        with self._vib_lock:
            self._vib_tokens[cid] += 1
            token = self._vib_tokens[cid]

        def _worker():
            self._set_vibration(xidx, left, right)
            end_t = time.time() + (max(0, int(duration_ms)) / 1000.0)
            while time.time() < end_t:
                with self._vib_lock:
                    if self._vib_tokens[cid] != token:
                        break
                time.sleep(0.01)
            with self._vib_lock:
                still_current = self._vib_tokens[cid] == token
            if still_current:
                self._set_vibration(xidx, 0, 0)

        threading.Thread(target=_worker, daemon=True).start()

    def run(self):
        while True:
            for idx in range(self.max_controllers):
                cid = self._xid(idx)
                gp = self._get_xinput_state(idx)
                if gp is None:
                    self.connected[cid] = False
                    self.latest[cid] = None
                    self.pressed[cid] = tuple()
                    if self.macro_engine is not None:
                        self.macro_engine.check_combo(cid, tuple())
                    if self.listen_armed and self._listen_controller == cid:
                        self.cancel_listen()
                    continue

                self.connected[cid] = True
                self.latest[cid] = gp
                self.names[cid] = f"XInput Controller {idx}"
                pressed_names = self._buttons_to_names(gp.wButtons)
                self.pressed[cid] = pressed_names
                if self.macro_engine is not None:
                    self.macro_engine.check_combo(cid, pressed_names)

            self._poll_pygame()

            for cid in [x for x in self._known_ids if x.startswith("pygame:") or x.startswith("inputs:")]:
                if self.macro_engine is not None:
                    self.macro_engine.check_combo(cid, self.pressed.get(cid, tuple()))

            if self.listen_armed:
                self._listen_tick()

            time.sleep(self.sleep_s)

    def get_known_ids(self):
        return list(self._known_ids)

    def get_connected_ids(self):
        return [cid for cid in self._known_ids if self.connected.get(cid)]

    def get_display_name(self, controller_id):
        cid = str(controller_id)
        return self.names.get(cid, cid)

    def get_gamepad(self, controller_id):
        return self.latest.get(str(controller_id))

    def get_pressed_combo(self, controller_id):
        return self.pressed.get(str(controller_id), tuple())


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
