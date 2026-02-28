import ctypes
import time
import threading
from ctypes import wintypes

try:
    import pygame
except Exception:
    pygame = None


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

PYGAME_BUTTON_MAP = {
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


class GenericGamepadState:
    def __init__(self):
        self.dwPacketNumber = int(time.time() * 1000) & 0xFFFFFFFF
        self.wButtons = 0
        self.bLeftTrigger = 0
        self.bRightTrigger = 0
        self.sThumbLX = 0
        self.sThumbLY = 0
        self.sThumbRX = 0
        self.sThumbRY = 0


class ControllerManager:
    """
    Polls up to 4 controllers across XInput and optional pygame devices.
    Stores latest states for UI, and sends combos to macro engine.
    Supports Listen Mode: press buttons (any order) + release -> captures FULL union combo
    from FIRST controller that presses.

    Also provides vibration feedback via XInputSetState for XInput-backed slots.
    """

    def __init__(self, macro_engine, max_controllers=4, poll_hz=100):
        self.macro_engine = macro_engine
        self.max_controllers = int(max_controllers)
        self.sleep_s = 1.0 / float(poll_hz)

        self.connected = {i: False for i in range(self.max_controllers)}
        self.latest = {i: None for i in range(self.max_controllers)}
        self.pressed = {i: tuple() for i in range(self.max_controllers)}
        self.slot_backend = {i: None for i in range(self.max_controllers)}

        self._source_slots = {}
        self._slot_sources = {i: None for i in range(self.max_controllers)}
        self._source_order = {}
        self._order_counter = 0
        self._slot_xinput = {i: None for i in range(self.max_controllers)}

        self._pygame_ready = False
        self._pygame_failed = False

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

    def _ensure_pygame(self):
        if self._pygame_ready or self._pygame_failed or pygame is None:
            return
        try:
            pygame.init()
            pygame.joystick.init()
            self._pygame_ready = True
        except Exception:
            self._pygame_failed = True

    def _axis_to_short(self, value):
        v = max(-1.0, min(1.0, float(value)))
        n = int(v * 32767)
        if n < -32768:
            n = -32768
        if n > 32767:
            n = 32767
        return n

    def _axis_to_trigger(self, value):
        v = float(value)
        # Some APIs provide [-1..1], others [0..1]
        if v < 0.0:
            v = (v + 1.0) / 2.0
        v = max(0.0, min(1.0, v))
        return int(v * 255)

    def _get_pygame_sources(self):
        out = {}
        self._ensure_pygame()
        if not self._pygame_ready:
            return out

        try:
            pygame.event.pump()
            count = pygame.joystick.get_count()
        except Exception:
            return out

        for idx in range(count):
            try:
                js = pygame.joystick.Joystick(idx)
                if not js.get_init():
                    js.init()

                inst_id = js.get_instance_id() if hasattr(js, "get_instance_id") else idx
                key = ("pygame", int(inst_id))
                state = GenericGamepadState()

                num_axes = js.get_numaxes()
                lx = js.get_axis(0) if num_axes > 0 else 0.0
                ly = js.get_axis(1) if num_axes > 1 else 0.0
                rx = js.get_axis(2) if num_axes > 2 else 0.0
                ry = js.get_axis(3) if num_axes > 3 else 0.0
                lt = js.get_axis(4) if num_axes > 4 else 0.0
                rt = js.get_axis(5) if num_axes > 5 else 0.0

                state.sThumbLX = self._axis_to_short(lx)
                state.sThumbLY = self._axis_to_short(-ly)
                state.sThumbRX = self._axis_to_short(rx)
                state.sThumbRY = self._axis_to_short(-ry)
                state.bLeftTrigger = self._axis_to_trigger(lt)
                state.bRightTrigger = self._axis_to_trigger(rt)

                pressed = set()
                for b_idx, b_name in PYGAME_BUTTON_MAP.items():
                    if b_idx < js.get_numbuttons() and js.get_button(b_idx):
                        pressed.add(b_name)

                for h_idx in range(js.get_numhats()):
                    hx, hy = js.get_hat(h_idx)
                    if hy > 0:
                        pressed.add("DPad Up")
                    elif hy < 0:
                        pressed.add("DPad Down")
                    if hx < 0:
                        pressed.add("DPad Left")
                    elif hx > 0:
                        pressed.add("DPad Right")

                out[key] = (state, tuple(sorted(pressed)), None, "pygame")
            except Exception:
                continue

        return out

    def _get_all_sources(self):
        sources = {}

        for xcid in range(self.max_controllers):
            gp = self._get_state(xcid)
            if gp is None:
                continue
            key = ("xinput", xcid)
            sources[key] = (gp, self._buttons_to_names(gp.wButtons), xcid, "xinput")

        sources.update(self._get_pygame_sources())
        return sources

    def _sync_slots(self, sources):
        active_keys = set(sources.keys())

        for key in list(self._source_slots.keys()):
            if key in active_keys:
                continue
            slot = self._source_slots.pop(key)
            self._slot_sources[slot] = None
            self.connected[slot] = False
            self.latest[slot] = None
            self.pressed[slot] = tuple()
            self.slot_backend[slot] = None
            self._slot_xinput[slot] = None
            if self.macro_engine is not None:
                self.macro_engine.check_combo(slot, tuple())
            if self.listen_armed and self._listen_controller == slot:
                self.cancel_listen()

        for key in active_keys:
            if key not in self._source_order:
                self._order_counter += 1
                self._source_order[key] = self._order_counter

        free_slots = [i for i in range(self.max_controllers) if self._slot_sources[i] is None]
        unassigned = [k for k in active_keys if k not in self._source_slots]
        unassigned.sort(key=lambda k: self._source_order.get(k, 0))

        for key in unassigned:
            if not free_slots:
                break
            slot = free_slots.pop(0)
            self._source_slots[key] = slot
            self._slot_sources[slot] = key

        for slot in range(self.max_controllers):
            key = self._slot_sources.get(slot)
            if key is None or key not in sources:
                continue
            gp, pressed_names, xinput_id, backend = sources[key]
            self.connected[slot] = True
            self.latest[slot] = gp
            self.pressed[slot] = pressed_names
            self.slot_backend[slot] = backend
            self._slot_xinput[slot] = xinput_id
            if self.macro_engine is not None:
                self.macro_engine.check_combo(slot, pressed_names)

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

        # If not connected or not an XInput-backed slot, do nothing
        if not self.connected.get(cid, False):
            return
        xinput_cid = self._slot_xinput.get(cid)
        if xinput_cid is None:
            return

        with self._vib_lock:
            self._vib_tokens[cid] += 1
            token = self._vib_tokens[cid]

        def _worker():
            # Start
            self._set_vibration(xinput_cid, left, right)
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
                self._set_vibration(xinput_cid, 0, 0)

        threading.Thread(target=_worker, daemon=True).start()

    # ---------------- Main Loop ----------------

    def run(self):
        while True:
            sources = self._get_all_sources()
            self._sync_slots(sources)

            if self.listen_armed:
                self._listen_tick()

            time.sleep(self.sleep_s)

    # ---------------- UI helpers ----------------

    def get_connected_ids(self):
        return [cid for cid in range(self.max_controllers) if self.connected.get(cid)]

    def get_backend(self, controller_id):
        return self.slot_backend.get(controller_id)

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
