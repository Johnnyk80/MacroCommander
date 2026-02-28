import tkinter as tk
from tkinter import ttk, filedialog, messagebox

STICK_MAX = 32768.0
TRIGGER_MAX = 255.0


def center_window_over_parent(child_win, parent_win, width, height):
    parent_win.update_idletasks()
    child_win.update_idletasks()

    px, py = parent_win.winfo_rootx(), parent_win.winfo_rooty()
    pw, ph = parent_win.winfo_width(), parent_win.winfo_height()

    x = px + (pw // 2) - (width // 2)
    y = py + (ph // 2) - (height // 2)

    sx, sy = parent_win.winfo_screenwidth(), parent_win.winfo_screenheight()
    x = max(0, min(x, sx - width))
    y = max(0, min(y, sy - height))

    child_win.geometry(f"{width}x{height}+{x}+{y}")


class ConfirmDialog:
    def __init__(self, parent, title, message):
        self.parent = parent
        self.result = False

        WIDTH = 420
        HEIGHT = 190

        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.resizable(False, False)

        center_window_over_parent(self.win, parent, WIDTH, HEIGHT)

        container = ttk.Frame(self.win, padding=14)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Confirm Deletion", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
        ttk.Label(container, text="Delete this macro?").pack(anchor="w", pady=(0, 6))

        combo_frame = ttk.LabelFrame(container, text="Macro Combo")
        combo_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(combo_frame, text=message.split("\n\n")[-1], font=("Segoe UI", 10)).pack(anchor="w", padx=8, pady=6)

        btn_row = ttk.Frame(container)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Cancel", command=self._no).pack(side="right", padx=(0, 6))
        ttk.Button(btn_row, text="Delete", command=self._yes).pack(side="right")

        self.win.bind("<Escape>", lambda _e: self._no())
        self.win.bind("<Return>", lambda _e: self._yes())
        self.win.protocol("WM_DELETE_WINDOW", self._no)

        self.win.after(0, lambda: self.win.focus_force())
        self.parent.wait_window(self.win)

    def _yes(self):
        self.result = True
        self.win.destroy()

    def _no(self):
        self.result = False
        self.win.destroy()


class ActivityLogWindow:
    def __init__(self, root, logger):
        self.root = root
        self.logger = logger

        self.win = tk.Toplevel(root)
        self.win.title("Activity Log (Debug)")
        self.win.transient(root)

        W, H = 900, 350
        center_window_over_parent(self.win, root, W, H)

        top = ttk.Frame(self.win)
        top.pack(fill="x", padx=8, pady=6)

        ttk.Button(top, text="Clear", command=self.clear).pack(side="left", padx=4)
        ttk.Button(top, text="Copy", command=self.copy_all).pack(side="left", padx=4)

        self.text = tk.Text(self.win, wrap="none", height=16)
        self.text.pack(fill="both", expand=True, padx=8, pady=6)
        self.text.configure(state="disabled")

        yscroll = ttk.Scrollbar(self.text, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=yscroll.set)
        yscroll.pack(side="right", fill="y")

        self._poll()

    def append_lines(self, lines):
        if not lines:
            return
        self.text.configure(state="normal")
        for line in lines:
            self.text.insert("end", line + "\n")
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def copy_all(self):
        data = self.text.get("1.0", "end").strip()
        self.win.clipboard_clear()
        self.win.clipboard_append(data)

    def _poll(self):
        try:
            lines = self.logger.drain(200) if self.logger else []
            self.append_lines(lines)
        except Exception:
            pass
        self.win.after(150, self._poll)


class ControllerMonitor(ttk.LabelFrame):
    def __init__(self, parent, controller_manager):
        super().__init__(parent, text="Controller Monitor")
        self.cm = controller_manager
        self.selected_controller = tk.IntVar(value=0)

        self.palette = {
            "bg": "#F5F7FB",
            "ink": "#1A1F2B",
            "muted": "#6D84A1",
            "line": "#C7D5E7",
            "accent": "#3D7EF4",
            "accent_soft": "#DDE9FF",
            "panel": "#FFFFFF",
        }

        self.inner = ttk.Frame(self)
        self.inner.pack(fill="both", expand=True, padx=8, pady=8)

        self.content = ttk.Frame(self.inner)
        self.content.place(relx=0.5, rely=0.0, anchor="n")

        top = ttk.Frame(self.content)
        top.pack(fill="x", padx=8, pady=6)

        ttk.Label(top, text="View Controller:").pack(side="left")
        self.controller_combo = ttk.Combobox(top, values=[0, 1, 2, 3], width=5, state="readonly")
        self.controller_combo.current(0)
        self.controller_combo.pack(side="left", padx=6)
        self.controller_combo.bind("<<ComboboxSelected>>", self._on_select)

        self.status_label = ttk.Label(top, text="Status: (waiting)")
        self.status_label.pack(side="left", padx=12)

        body = tk.Frame(
            self.content,
            bg=self.palette["bg"],
            highlightthickness=1,
            highlightbackground=self.palette["line"],
            width=880,
            height=470,
        )
        body.pack(fill="both", expand=True, padx=8, pady=(4, 24))
        body.pack_propagate(False)

        self.xinput_frame = tk.Frame(body, bg=self.palette["bg"])
        self.xinput_frame.pack(fill="both", expand=True, padx=20, pady=16)

        header = tk.Frame(self.xinput_frame, bg=self.palette["bg"])
        header.pack(fill="x")
        tk.Label(header, text="xinput", font=("Segoe UI", 34, "bold"), fg=self.palette["ink"], bg=self.palette["bg"]).pack(anchor="w")

        metrics = tk.Frame(self.xinput_frame, bg=self.palette["bg"])
        metrics.pack(fill="x", pady=(10, 14))
        self.metric_values = {}
        metric_cols = [("INDEX", "index"), ("CONNECTED", "connected"), ("MAPPING", "mapping"), ("TIMESTAMP", "timestamp")]
        for col, (label, key) in enumerate(metric_cols):
            cell = tk.Frame(metrics, bg=self.palette["bg"])
            cell.grid(row=0, column=col, padx=(0, 32), sticky="w")
            tk.Label(cell, text=label, font=("Segoe UI", 9), fg=self.palette["muted"], bg=self.palette["bg"]).pack(anchor="w")
            value = tk.Label(cell, text="-", font=("Segoe UI", 14, "bold"), fg=self.palette["ink"], bg=self.palette["bg"])
            value.pack(anchor="w")
            self.metric_values[key] = value

        button_grid = tk.Frame(self.xinput_frame, bg=self.palette["bg"])
        button_grid.pack(fill="x", pady=(0, 12))
        self.button_labels = {}
        button_order = ["A", "B", "X", "Y", "LB", "RB", "Back", "Start", "LS", "RS", "DPad Up", "DPad Down", "DPad Left", "DPad Right"]
        for i, name in enumerate(button_order):
            cell = tk.Frame(button_grid, bg=self.palette["bg"])
            cell.grid(row=i // 7, column=i % 7, padx=4, pady=4, sticky="w")
            tk.Label(cell, text=name, font=("Segoe UI", 8), fg=self.palette["muted"], bg=self.palette["bg"]).pack(anchor="w")
            lbl = tk.Label(
                cell,
                text="0.00",
                width=6,
                anchor="w",
                font=("Consolas", 10, "bold"),
                fg=self.palette["ink"],
                bg=self.palette["panel"],
                relief="flat",
            )
            lbl.pack(anchor="w")
            self.button_labels[name] = lbl

        lower = tk.Frame(self.xinput_frame, bg=self.palette["bg"])
        lower.pack(fill="both", expand=True)

        trig = tk.Frame(lower, bg=self.palette["bg"])
        trig.pack(side="left", fill="both", expand=True, padx=(0, 16), anchor="n")

        tk.Label(trig, text="L TRIGGER", bg=self.palette["bg"], fg=self.palette["muted"], font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        self.lt_canvas = tk.Canvas(trig, width=300, height=16, bg=self.palette["panel"], highlightthickness=1, highlightbackground=self.palette["line"])
        self.lt_canvas.grid(row=1, column=0, sticky="w", pady=(2, 10))
        self.lt_bar = self.lt_canvas.create_rectangle(0, 0, 0, 16, fill=self.palette["accent"], width=0)

        tk.Label(trig, text="R TRIGGER", bg=self.palette["bg"], fg=self.palette["muted"], font=("Segoe UI", 10)).grid(row=2, column=0, sticky="w")
        self.rt_canvas = tk.Canvas(trig, width=300, height=16, bg=self.palette["panel"], highlightthickness=1, highlightbackground=self.palette["line"])
        self.rt_canvas.grid(row=3, column=0, sticky="w", pady=(2, 0))
        self.rt_bar = self.rt_canvas.create_rectangle(0, 0, 0, 16, fill=self.palette["accent"], width=0)

        sticks = tk.Frame(lower, bg=self.palette["bg"])
        sticks.pack(side="left", fill="both", expand=True, anchor="n")

        self.left_canvas = tk.Canvas(sticks, width=160, height=160, bg=self.palette["bg"], highlightthickness=0)
        self.left_canvas.grid(row=0, column=0, padx=(0, 18))
        self.right_canvas = tk.Canvas(sticks, width=160, height=160, bg=self.palette["bg"], highlightthickness=0)
        self.right_canvas.grid(row=0, column=1)

        for c in (self.left_canvas, self.right_canvas):
            c.create_oval(10, 10, 150, 150, outline=self.palette["line"], width=1)
            c.create_line(80, 10, 80, 150, fill=self.palette["line"])
            c.create_line(10, 80, 150, 80, fill=self.palette["line"])

        self.left_dot = self.left_canvas.create_oval(75, 75, 85, 85, fill=self.palette["accent"], outline="")
        self.right_dot = self.right_canvas.create_oval(75, 75, 85, 85, fill=self.palette["accent"], outline="")

        self.bluetooth_frame = tk.Frame(body, bg=self.palette["bg"])
        self._build_bluetooth_layout(self.bluetooth_frame)

        self.disconnected_frame = tk.Frame(body, bg=self.palette["bg"])
        self.disconnected_label = tk.Label(
            self.disconnected_frame,
            text="Controller disconnected",
            font=("Segoe UI", 18, "bold"),
            fg=self.palette["muted"],
            bg=self.palette["bg"],
        )
        self.disconnected_label.pack(expand=True)

    def _build_bluetooth_layout(self, parent):
        header = tk.Frame(parent, bg=self.palette["bg"])
        header.pack(fill="x", pady=(0, 8))
        self.bt_title = tk.Label(header, text="Bluetooth / Generic Controller", font=("Segoe UI", 20, "bold"), fg=self.palette["ink"], bg=self.palette["bg"])
        self.bt_title.pack(anchor="w")

        axes = tk.LabelFrame(parent, text="Axes", bg=self.palette["bg"], fg=self.palette["ink"])
        axes.pack(fill="x", pady=(0, 8))

        axis_row = tk.Frame(axes, bg=self.palette["bg"])
        axis_row.pack(fill="x", padx=8, pady=8)

        self.bt_xy = tk.Canvas(axis_row, width=120, height=120, bg=self.palette["panel"], highlightthickness=1, highlightbackground=self.palette["line"])
        self.bt_xy.pack(side="left", padx=(0, 12))
        self.bt_xy.create_line(60, 10, 60, 110, fill=self.palette["line"])
        self.bt_xy.create_line(10, 60, 110, 60, fill=self.palette["line"])
        self.bt_xy_dot = self.bt_xy.create_oval(56, 56, 64, 64, fill=self.palette["accent"], outline="")

        bars = tk.Frame(axis_row, bg=self.palette["bg"])
        bars.pack(side="left", fill="x", expand=True)
        tk.Label(bars, text="Z Axis", bg=self.palette["bg"], fg=self.palette["muted"]).grid(row=0, column=0, sticky="w")
        self.bt_z_canvas = tk.Canvas(bars, width=280, height=16, bg=self.palette["panel"], highlightthickness=1, highlightbackground=self.palette["line"])
        self.bt_z_canvas.grid(row=0, column=1, padx=8, pady=4, sticky="w")
        self.bt_z_bar = self.bt_z_canvas.create_rectangle(0, 0, 0, 16, fill=self.palette["accent"], width=0)

        tk.Label(bars, text="Z Rotation", bg=self.palette["bg"], fg=self.palette["muted"]).grid(row=1, column=0, sticky="w")
        self.bt_r_canvas = tk.Canvas(bars, width=280, height=16, bg=self.palette["panel"], highlightthickness=1, highlightbackground=self.palette["line"])
        self.bt_r_canvas.grid(row=1, column=1, padx=8, pady=4, sticky="w")
        self.bt_r_bar = self.bt_r_canvas.create_rectangle(0, 0, 0, 16, fill=self.palette["accent"], width=0)

        lower = tk.Frame(parent, bg=self.palette["bg"])
        lower.pack(fill="both", expand=True)

        btn_box = tk.LabelFrame(lower, text="Buttons", bg=self.palette["bg"], fg=self.palette["ink"])
        btn_box.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.bt_button_labels = {}
        for i in range(16):
            n = i + 1
            row, col = divmod(i, 8)
            c = tk.Canvas(btn_box, width=30, height=30, bg=self.palette["bg"], highlightthickness=0)
            c.grid(row=row, column=col, padx=6, pady=8)
            oval = c.create_oval(4, 4, 26, 26, fill="#7A0000", outline="#300")
            text = c.create_text(15, 15, text=str(n), fill="white", font=("Segoe UI", 9, "bold"))
            self.bt_button_labels[n] = (c, oval, text)

        pov_box = tk.LabelFrame(lower, text="Point of View Hat", bg=self.palette["bg"], fg=self.palette["ink"])
        pov_box.pack(side="left", fill="both", padx=(8, 0))
        self.bt_pov = tk.Canvas(pov_box, width=130, height=130, bg=self.palette["panel"], highlightthickness=1, highlightbackground=self.palette["line"])
        self.bt_pov.pack(padx=10, pady=10)
        self.bt_pov.create_oval(15, 15, 115, 115, outline=self.palette["line"])
        self.bt_pov_dot = self.bt_pov.create_oval(60, 60, 70, 70, fill=self.palette["accent"], outline="")

    def _set_metric(self, key, value):
        lbl = self.metric_values.get(key)
        if lbl is not None:
            lbl.config(text=value)

    def _on_select(self, _evt=None):
        try:
            self.selected_controller.set(int(self.controller_combo.get()))
        except Exception:
            self.selected_controller.set(0)

    def _set_bar(self, canvas, bar, value_0_255):
        try:
            pct = float(value_0_255) / TRIGGER_MAX
        except Exception:
            pct = 0.0
        pct = max(0.0, min(1.0, pct))
        width = int(canvas.cget("width"))
        canvas.coords(bar, 0, 0, int(width * pct), 16)

    def _set_stick(self, canvas, dot, x, y):
        nx = float(x) / STICK_MAX
        ny = -float(y) / STICK_MAX
        center, radius = 80, 60
        dx = center + (nx * radius)
        dy = center + (ny * radius)
        canvas.coords(dot, dx - 5, dy - 5, dx + 5, dy + 5)

    def _set_signed_axis_bar(self, canvas, bar, value):
        try:
            v = float(value) / STICK_MAX
        except Exception:
            v = 0.0
        v = max(-1.0, min(1.0, v))
        width = int(canvas.cget("width"))
        center = width // 2
        x = int(center + (center * v))
        left = min(center, x)
        right = max(center, x)
        canvas.coords(bar, left, 0, right, 16)

    def _set_generic_button(self, number, pressed):
        item = self.bt_button_labels.get(number)
        if not item:
            return
        c, oval, _ = item
        c.itemconfig(oval, fill="#C50000" if pressed else "#7A0000")

    def _set_pov(self, pressed_names):
        x, y = 65, 65
        step = 30
        if "DPad Left" in pressed_names:
            x -= step
        if "DPad Right" in pressed_names:
            x += step
        if "DPad Up" in pressed_names:
            y -= step
        if "DPad Down" in pressed_names:
            y += step
        self.bt_pov.coords(self.bt_pov_dot, x - 5, y - 5, x + 5, y + 5)

    def _set_xy_dot(self, x, y):
        nx = float(x) / STICK_MAX
        ny = -float(y) / STICK_MAX
        cx, cy, radius = 60, 60, 45
        dx = cx + (nx * radius)
        dy = cy + (ny * radius)
        self.bt_xy.coords(self.bt_xy_dot, dx - 4, dy - 4, dx + 4, dy + 4)

    def update_view(self):
        cid = self.selected_controller.get()
        connected = cid in self.cm.get_connected_ids()

        self._set_metric("index", str(cid))
        self._set_metric("mapping", "xinput")

        self.bluetooth_frame.pack_forget()
        self.xinput_frame.pack_forget()
        self.disconnected_frame.pack_forget()

        if not connected:
            self.status_label.config(text=f"Status: Controller {cid} not connected")
            self._set_metric("connected", "No")
            self._set_metric("mapping", "-")
            self._set_metric("timestamp", "-")
            self.disconnected_frame.pack(fill="both", expand=True, padx=20, pady=16)
            for lbl in self.button_labels.values():
                lbl.config(text="0.00", bg=self.palette["panel"], fg=self.palette["ink"])
            self._set_bar(self.lt_canvas, self.lt_bar, 0)
            self._set_bar(self.rt_canvas, self.rt_bar, 0)
            self._set_stick(self.left_canvas, self.left_dot, 0, 0)
            self._set_stick(self.right_canvas, self.right_dot, 0, 0)
            self._set_xy_dot(0, 0)
            self._set_signed_axis_bar(self.bt_z_canvas, self.bt_z_bar, 0)
            self._set_signed_axis_bar(self.bt_r_canvas, self.bt_r_bar, 0)
            self._set_pov(set())
            for i in range(1, 17):
                self._set_generic_button(i, False)
            return

        gp = self.cm.get_gamepad(cid)
        pressed = set(self.cm.get_pressed_combo(cid))

        self.status_label.config(text=f"Status: Controller {cid} connected (XInput Controller {cid})")
        self._set_metric("connected", "Yes")
        self._set_metric("mapping", "xinput")
        self._set_metric("timestamp", f"{getattr(gp, 'dwPacketNumber', 0)}")

        self.xinput_frame.pack(fill="both", expand=True, padx=20, pady=16)
        for name, lbl in self.button_labels.items():
            is_pressed = name in pressed
            lbl.config(
                text="1.00" if is_pressed else "0.00",
                bg=self.palette["accent_soft"] if is_pressed else self.palette["panel"],
                fg=self.palette["accent"] if is_pressed else self.palette["ink"],
            )

        if gp is None:
            return

        self._set_bar(self.lt_canvas, self.lt_bar, gp.bLeftTrigger)
        self._set_bar(self.rt_canvas, self.rt_bar, gp.bRightTrigger)
        self._set_stick(self.left_canvas, self.left_dot, gp.sThumbLX, gp.sThumbLY)
        self._set_stick(self.right_canvas, self.right_dot, gp.sThumbRX, gp.sThumbRY)


class MacroPanel(ttk.LabelFrame):
    def __init__(self, parent, macro_engine, controller_manager, registry):
        super().__init__(parent, text="Macros")
        self.engine = macro_engine
        self.cm = controller_manager
        self.registry = registry

        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(
            header,
            text="Right-click inside the macro list to add, edit, activate, or delete macros.",
            font=("Segoe UI", 9),
            foreground="gray"
        ).pack(anchor="w")

        self.tree_container = ttk.Frame(self)
        self.tree_container.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        self.tree = ttk.Treeview(
            self.tree_container,
            columns=("Combo", "Controllers", "Hold", "Steps", "Active"),
            show="headings",
            height=6
        )
        self.tree.heading("Combo", text="Combo")
        self.tree.heading("Controllers", text="Controllers")
        self.tree.heading("Hold", text="Hold")
        self.tree.heading("Steps", text="Steps")
        self.tree.heading("Active", text="Active")

        self.tree.column("Combo", width=180, stretch=False)
        self.tree.column("Controllers", width=180, stretch=False)
        self.tree.column("Hold", width=70, stretch=False)
        self.tree.column("Steps", width=300, stretch=True)
        self.tree.column("Active", width=70, stretch=False)

        self.vscroll = ttk.Scrollbar(self.tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.vscroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        self.vscroll.pack(side="right", fill="y")

        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Add Macro", command=self.open_add_dialog)
        self.menu.add_separator()
        self.menu.add_command(label="Edit", command=self._ctx_edit)
        self.menu.add_command(label="Activate", command=self._ctx_toggle_active)
        self.menu.add_command(label="Delete", command=self._ctx_delete)

        self._idx_edit = 2
        self._idx_toggle = 3
        self._idx_delete = 4

        self.tree.bind("<Button-3>", self._on_right_click)
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for m in self.engine.macros:
            combo_str = " + ".join(m.get("combo", []))
            hold = float(m.get("hold_seconds", 0.0))
            active_txt = "✔" if bool(m.get("active", True)) else "✘"
            allowed = m.get("allowed_controllers", [0, 1, 2, 3])
            if sorted(allowed) == [0, 1, 2, 3]:
                controllers_txt = "All (1-4)"
            else:
                controllers_txt = ", ".join(f"C{int(c)+1}" for c in allowed)

            steps = m.get("steps", [])
            if not isinstance(steps, list):
                steps = []

            parts = []
            for s in steps:
                if str(s.get("kind", "")).lower() == "wait":
                    parts.append(f"Wait {float(s.get('seconds', 0.0)):g}s")
                else:
                    aid = s.get("action_id", "")
                    parts.append(self.registry.get_name(aid))
            steps_summary = "  →  ".join(parts) if parts else "(no steps)"

            mid = m.get("id")
            self.tree.insert("", "end", iid=str(mid), values=(combo_str, controllers_txt, hold, steps_summary, active_txt))

    def _get_selected_macro_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def _on_right_click(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.tree.focus(row)
        else:
            self.tree.selection_remove(self.tree.selection())

        mid = self._get_selected_macro_id()
        if mid is None:
            self.menu.entryconfig(self._idx_edit, state="disabled")
            self.menu.entryconfig(self._idx_delete, state="disabled")
            self.menu.entryconfig(self._idx_toggle, state="disabled")
            self.menu.entryconfig(self._idx_toggle, label="Activate")
        else:
            macro = self.engine.get_macro_by_id(mid)
            if not macro:
                self.menu.entryconfig(self._idx_edit, state="disabled")
                self.menu.entryconfig(self._idx_delete, state="disabled")
                self.menu.entryconfig(self._idx_toggle, state="disabled")
                self.menu.entryconfig(self._idx_toggle, label="Activate")
            else:
                self.menu.entryconfig(self._idx_edit, state="normal")
                self.menu.entryconfig(self._idx_delete, state="normal")
                self.menu.entryconfig(self._idx_toggle, state="normal")
                self.menu.entryconfig(self._idx_toggle, label="Deactivate" if macro.get("active", True) else "Activate")

        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _ctx_edit(self):
        mid = self._get_selected_macro_id()
        if mid is None:
            return
        macro = self.engine.get_macro_by_id(mid)
        if not macro:
            return
        self._open_macro_dialog(mode="edit", macro_id=mid, macro=macro)

    def _ctx_toggle_active(self):
        mid = self._get_selected_macro_id()
        if mid is None:
            return
        macro = self.engine.get_macro_by_id(mid)
        if not macro:
            return
        self.engine.set_macro_active(mid, not bool(macro.get("active", True)))
        self.refresh()

    def _ctx_delete(self):
        mid = self._get_selected_macro_id()
        if mid is None:
            return
        macro = self.engine.get_macro_by_id(mid)
        if not macro:
            return

        combo_str = " + ".join(macro.get("combo", []))
        msg = f"Delete this macro?\n\n{combo_str}"

        dlg = ConfirmDialog(self.winfo_toplevel(), "Delete Macro", msg)
        if not dlg.result:
            return

        self.engine.remove_macro_by_id(mid)
        self.refresh()

    def open_add_dialog(self):
        self._open_macro_dialog(mode="add", macro_id=None, macro=None)

    def _center_modal_over_parent(self, dlg, width, height):
        parent = self.winfo_toplevel()
        center_window_over_parent(dlg, parent, width, height)

    # ---------- Action UI helpers ----------

    def _build_param_fields(self, parent, schema: dict, initial_params: dict):
        """
        Creates fields based on schema.
        Supported types: string, float, bool, file, choice, slider
        Returns dict: key -> (type, var, meta)
        """
        widgets = {}
        r = 0

        for key, meta in (schema or {}).items():
            ftype = str(meta.get("type", "string")).lower().strip()
            label = str(meta.get("label", key)).strip()
            required = bool(meta.get("required", False))

            ttk.Label(parent, text=label + ("" if not required else " *")).grid(row=r, column=0, sticky="w", padx=(0, 8), pady=6)

            if ftype == "bool":
                var = tk.BooleanVar(value=bool(initial_params.get(key, meta.get("default", False))))
                cb = ttk.Checkbutton(parent, variable=var)
                cb.grid(row=r, column=1, sticky="w", pady=6)
                widgets[key] = ("bool", var, meta)
                r += 1
                continue

            if ftype == "choice":
                live_meta = {**meta}
                options_provider = live_meta.get("options_provider")

                def _normalize_options(opts):
                    labels = []
                    value_by_label = {}
                    for opt in (opts or []):
                        if isinstance(opt, dict):
                            value = str(opt.get("value", ""))
                            label_txt = str(opt.get("label", value))
                        else:
                            value = str(opt)
                            label_txt = value
                        if not value:
                            continue
                        labels.append(label_txt)
                        value_by_label[label_txt] = value
                    return labels, value_by_label

                labels, value_by_label = _normalize_options(live_meta.get("options", []) or [])

                initial_val = str(initial_params.get(key, live_meta.get("default", "")) or "")
                initial_label = next((lbl for lbl, val in value_by_label.items() if val == initial_val), "")
                if not initial_label and labels:
                    initial_label = labels[0]

                var = tk.StringVar(value=initial_label)

                def _refresh_choice(v=var, m=live_meta):
                    provider = m.get("options_provider")
                    if not callable(provider):
                        return
                    try:
                        fresh = provider()
                    except Exception:
                        return

                    current_value = m.get("_value_by_label", {}).get(str(v.get()).strip(), "")
                    new_labels, new_value_by_label = _normalize_options(fresh)
                    m["_value_by_label"] = new_value_by_label
                    cmb.configure(values=new_labels)

                    next_label = next((lbl for lbl, val in new_value_by_label.items() if val == current_value), "")
                    if not next_label and new_labels:
                        next_label = new_labels[0]
                    v.set(next_label)

                cmb = ttk.Combobox(parent, textvariable=var, values=labels, state="readonly", width=56, postcommand=_refresh_choice)
                cmb.grid(row=r, column=1, sticky="ew", pady=6)
                cmb.bind("<FocusIn>", lambda _e, fn=_refresh_choice: fn())

                live_meta["_value_by_label"] = value_by_label
                widgets[key] = ("choice", var, live_meta)
                r += 1
                continue

            if ftype == "slider":
                min_v = float(meta.get("min", 0))
                max_v = float(meta.get("max", 100))
                step = float(meta.get("step", 1))
                default_v = float(initial_params.get(key, meta.get("default", min_v)))
                default_v = max(min_v, min(max_v, default_v))

                var = tk.DoubleVar(value=default_v)
                slider_frame = ttk.Frame(parent)
                slider_frame.grid(row=r, column=1, sticky="ew", pady=6)
                slider_frame.columnconfigure(0, weight=1)

                value_label = ttk.Label(slider_frame, width=4, text=str(int(round(default_v))))

                def _on_slide(_v=None, value_var=var, out=value_label, s=step):
                    value = float(value_var.get())
                    if s > 0:
                        value = round(value / s) * s
                    value_var.set(value)
                    out.config(text=str(int(round(value))))

                scale = ttk.Scale(slider_frame, from_=min_v, to=max_v, variable=var, orient="horizontal", command=_on_slide)
                scale.grid(row=0, column=0, sticky="ew")
                value_label.grid(row=0, column=1, padx=(8, 0))
                _on_slide()

                widgets[key] = ("slider", var, meta)
                r += 1
                continue

            # string/float/file
            var = tk.StringVar(value=str(initial_params.get(key, meta.get("default", "")) or ""))
            entry = ttk.Entry(parent, textvariable=var, width=58)
            entry.grid(row=r, column=1, sticky="ew", pady=6)

            if ftype == "file":
                def _browse(k=key, v=var, m=meta):
                    filetypes = m.get("filetypes")
                    if not filetypes:
                        filetypes = [("All files", "*.*")]
                    path = filedialog.askopenfilename(filetypes=filetypes)
                    if path:
                        v.set(path)

                ttk.Button(parent, text="Browse", command=_browse).grid(row=r, column=2, padx=(8, 0), pady=6)

            widgets[key] = (ftype, var, meta)
            r += 1

        parent.columnconfigure(1, weight=1)
        return widgets

    def _params_from_widgets(self, widgets: dict):
        params = {}
        for key, (ftype, var, meta) in (widgets or {}).items():
            if ftype == "bool":
                params[key] = bool(var.get())
            elif ftype == "float":
                try:
                    params[key] = float(var.get())
                except Exception:
                    params[key] = 0.0
            elif ftype == "choice":
                label = str(var.get()).strip()
                value_by_label = meta.get("_value_by_label", {}) if isinstance(meta, dict) else {}
                params[key] = str(value_by_label.get(label, label)).strip()
            elif ftype == "slider":
                try:
                    params[key] = float(var.get())
                except Exception:
                    params[key] = 0.0
            else:
                params[key] = str(var.get()).strip()
        return params

    def _validate_params(self, schema: dict, params: dict):
        for key, meta in (schema or {}).items():
            if bool(meta.get("required", False)):
                v = params.get(key, None)
                if v is None:
                    return False, f"Missing required field: {key}"
                if isinstance(v, str) and not v.strip():
                    return False, f"Missing required field: {key}"
        return True, ""

    def _step_dialog_run(self, parent, initial=None):
        """
        Run step dialog: choose an action from registry + fill its params from schema.
        """
        dlg = tk.Toplevel(parent)
        dlg.title("Add Step" if initial is None else "Edit Step")
        dlg.transient(parent)
        dlg.grab_set()
        self._center_modal_over_parent(dlg, 720, 380)

        dlg.minsize(720, 380)
        dlg.resizable(True, True)

        actions = self.registry.list_actions()
        if not actions:
            messagebox.showerror("Run Step", "No actions registered.")
            dlg.destroy()
            return None

        # Build list for display
        display = [f"{a.name}   ({a.action_id})" for a in actions]
        id_by_display = {display[i]: actions[i].action_id for i in range(len(actions))}

        initial_action_id = ""
        initial_params = {}
        if initial:
            initial_action_id = str(initial.get("action_id", "")).strip()
            initial_params = initial.get("params", {}) if isinstance(initial.get("params", {}), dict) else {}

        # Select initial index
        initial_choice = display[0]
        for d in display:
            if id_by_display[d] == initial_action_id:
                initial_choice = d
                break

        top = ttk.Frame(dlg, padding=12)
        top.pack(fill="x")

        ttk.Label(top, text="Action:").grid(row=0, column=0, sticky="w")
        choice_var = tk.StringVar(value=initial_choice)
        cmb = ttk.Combobox(top, textvariable=choice_var, values=display, state="readonly", width=60)
        cmb.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        top.columnconfigure(1, weight=1)

        desc = ttk.Label(dlg, text="", foreground="gray")
        desc.pack(anchor="w", padx=12, pady=(0, 6))

        fields_frame = ttk.LabelFrame(dlg, text="Parameters")
        fields_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        widgets = {"_map": {}}

        def render_fields():
            # Clear frame
            for w in fields_frame.winfo_children():
                w.destroy()

            action_id = id_by_display.get(choice_var.get(), actions[0].action_id)
            action = self.registry.get(action_id)
            if not action:
                desc.config(text="(Action not found)")
                widgets["_map"] = {}
                return

            desc.config(text=action.description or "")
            inner = ttk.Frame(fields_frame, padding=10)
            inner.pack(fill="both", expand=True)

            widgets["_map"] = self._build_param_fields(inner, action.schema, initial_params if action_id == initial_action_id else {})

        cmb.bind("<<ComboboxSelected>>", lambda _e: render_fields())
        render_fields()

        result = {"ok": False, "step": None}

        def save():
            action_id = id_by_display.get(choice_var.get(), "")
            action = self.registry.get(action_id)
            if not action:
                messagebox.showerror("Run Step", "Invalid action selected.")
                return

            params = self._params_from_widgets(widgets.get("_map", {}))
            ok, err = self._validate_params(action.schema, params)
            if not ok:
                messagebox.showerror("Run Step", err)
                return

            result["ok"] = True
            result["step"] = {"kind": "run", "action_id": action_id, "params": params}
            dlg.destroy()

        def cancel():
            dlg.destroy()

        btns = ttk.Frame(dlg, padding=12)
        btns.pack(fill="x")
        ttk.Button(btns, text="OK", command=save).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text="Cancel", command=cancel).pack(side="right")

        dlg.protocol("WM_DELETE_WINDOW", cancel)
        dlg.wait_window()

        return result["step"] if result["ok"] else None

    def _step_dialog_wait(self, parent, initial=None):
        dlg = tk.Toplevel(parent)
        dlg.title("Wait Step")
        dlg.transient(parent)
        dlg.grab_set()
        self._center_modal_over_parent(dlg, 420, 180)

        sec_var = tk.StringVar(value="1.0")
        if initial:
            sec_var.set(str(initial.get("seconds", 1.0)))

        ttk.Label(dlg, text="Wait (seconds):").grid(row=0, column=0, sticky="w", padx=12, pady=14)
        ttk.Entry(dlg, textvariable=sec_var, width=12).grid(row=0, column=1, sticky="w", padx=12, pady=14)

        result = {"ok": False, "step": None}

        def save():
            try:
                secs = float(sec_var.get().strip())
                if secs < 0:
                    secs = 0.0
            except Exception:
                secs = 0.0
            result["ok"] = True
            result["step"] = {"kind": "wait", "seconds": secs}
            dlg.destroy()

        def cancel():
            dlg.destroy()

        btns = ttk.Frame(dlg)
        btns.grid(row=1, column=0, columnspan=2, pady=10)

        ttk.Button(btns, text="OK", command=save).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancel", command=cancel).pack(side="left", padx=6)

        dlg.protocol("WM_DELETE_WINDOW", cancel)
        dlg.wait_window()

        return result["step"] if result["ok"] else None

    # ---------- Macro dialog ----------

    def _open_macro_dialog(self, mode, macro_id, macro):
        dlg = tk.Toplevel(self)
        dlg.title("Add Macro" if mode == "add" else "Edit Macro")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        W, H = 920, 560
        self._center_modal_over_parent(dlg, W, H)
        dlg.minsize(920, 560)
        dlg.resizable(True, True)

        combo_var = tk.StringVar(value="")
        hold_var = tk.StringVar(value="0")
        active_var = tk.BooleanVar(value=True)

        steps = []

        if mode == "edit" and macro:
            combo_var.set(" + ".join(macro.get("combo", [])))
            hold_var.set(str(macro.get("hold_seconds", 0.0)))
            active_var.set(bool(macro.get("active", True)))

            st = macro.get("steps", [])
            if isinstance(st, list):
                steps = [dict(x) for x in st]

        listen_btn_text = tk.StringVar(value="Listen Combo")
        listening = {"on": False}

        top = ttk.Frame(dlg)
        top.pack(fill="x", padx=12, pady=12)
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Combo:").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=combo_var).grid(row=0, column=1, sticky="ew", padx=10)

        def listen_here():
            if listening["on"]:
                listening["on"] = False
                listen_btn_text.set("Listen Combo")
                self.cm.cancel_listen()
                return

            listening["on"] = True
            listen_btn_text.set("Listening...")

            def on_captured(cid, combo):
                def _apply():
                    listening["on"] = False
                    listen_btn_text.set("Listen Combo")
                    combo_var.set(" + ".join(combo))
                dlg.after(0, _apply)

            self.cm.arm_listen(on_captured)

        ttk.Button(top, textvariable=listen_btn_text, command=listen_here).grid(row=0, column=2, padx=10)

        ttk.Label(top, text="Hold (seconds):").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(top, textvariable=hold_var, width=10).grid(row=1, column=1, sticky="w", padx=10, pady=(10, 0))
        ttk.Checkbutton(top, text="Active", variable=active_var).grid(row=1, column=2, sticky="w", padx=10, pady=(10, 0))

        selector = ttk.LabelFrame(dlg, text="Allowed Controllers", padding=10)
        selector.pack(fill="x", padx=12, pady=(0, 12))

        controller_vars = []
        labels = ["Controller 1", "Controller 2", "Controller 3", "Controller 4"]
        initial_allowed = [0, 1, 2, 3]
        if mode == "edit" and macro:
            initial_allowed = macro.get("allowed_controllers", [0, 1, 2, 3])

        for i, label in enumerate(labels):
            var = tk.BooleanVar(value=(i in initial_allowed))
            controller_vars.append(var)
            ttk.Checkbutton(selector, text=label, variable=var).grid(row=0, column=i, sticky="w", padx=(0, 14))

        all_var = tk.BooleanVar(value=all(v.get() for v in controller_vars))

        def apply_all():
            checked = all_var.get()
            for var in controller_vars:
                var.set(checked)

        def refresh_all():
            all_var.set(all(v.get() for v in controller_vars))

        ttk.Checkbutton(selector, text="All Controllers", variable=all_var, command=apply_all).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        for var in controller_vars:
            var.trace_add("write", lambda *_: refresh_all())

        steps_frame = ttk.LabelFrame(dlg, text="Steps (executed in order)")
        steps_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        steps_frame.columnconfigure(0, weight=1)
        steps_frame.rowconfigure(0, weight=1)

        steps_tree = ttk.Treeview(steps_frame, columns=("Kind", "Detail"), show="headings", height=10)
        steps_tree.heading("Kind", text="Step")
        steps_tree.heading("Detail", text="Details")
        steps_tree.column("Kind", width=90, stretch=False)
        steps_tree.column("Detail", width=640, stretch=True)
        steps_tree.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)

        scroll = ttk.Scrollbar(steps_frame, orient="vertical", command=steps_tree.yview)
        steps_tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns", pady=10)

        btncol = ttk.Frame(steps_frame)
        btncol.grid(row=0, column=2, sticky="ns", padx=(10, 10), pady=10)
        btncol.grid_propagate(False)
        btncol.configure(width=130)

        def render_steps():
            for item in steps_tree.get_children():
                steps_tree.delete(item)

            for i, s in enumerate(steps):
                kind = str(s.get("kind", "run")).lower()
                if kind == "wait":
                    steps_tree.insert("", "end", iid=str(i), values=("WAIT", f"{float(s.get('seconds', 0.0)):g} seconds"))
                else:
                    aid = s.get("action_id", "")
                    steps_tree.insert("", "end", iid=str(i), values=("RUN", self.registry.get_name(aid)))

        def get_sel_index():
            sel = steps_tree.selection()
            if not sel:
                return None
            try:
                return int(sel[0])
            except Exception:
                return None

        def add_run():
            step = self._step_dialog_run(dlg, initial=None)
            if step:
                steps.append(step)
                render_steps()

        def add_wait():
            step = self._step_dialog_wait(dlg, initial=None)
            if step:
                steps.append(step)
                render_steps()

        def edit_step():
            idx = get_sel_index()
            if idx is None or idx < 0 or idx >= len(steps):
                return
            cur = steps[idx]
            if str(cur.get("kind", "run")).lower() == "wait":
                step = self._step_dialog_wait(dlg, initial=cur)
            else:
                step = self._step_dialog_run(dlg, initial=cur)
            if step:
                steps[idx] = step
                render_steps()
                steps_tree.selection_set(str(idx))

        def remove_step():
            idx = get_sel_index()
            if idx is None or idx < 0 or idx >= len(steps):
                return
            steps.pop(idx)
            render_steps()

        def move_up():
            idx = get_sel_index()
            if idx is None or idx <= 0:
                return
            steps[idx - 1], steps[idx] = steps[idx], steps[idx - 1]
            render_steps()
            steps_tree.selection_set(str(idx - 1))

        def move_down():
            idx = get_sel_index()
            if idx is None or idx >= len(steps) - 1:
                return
            steps[idx + 1], steps[idx] = steps[idx], steps[idx + 1]
            render_steps()
            steps_tree.selection_set(str(idx + 1))

        ttk.Button(btncol, text="Add Step…", command=add_run).pack(fill="x", pady=(0, 6))
        ttk.Button(btncol, text="Add Wait…", command=add_wait).pack(fill="x", pady=(0, 12))
        ttk.Button(btncol, text="Edit", command=edit_step).pack(fill="x", pady=(0, 6))
        ttk.Button(btncol, text="Remove", command=remove_step).pack(fill="x", pady=(0, 12))
        ttk.Button(btncol, text="Move Up", command=move_up).pack(fill="x", pady=(0, 6))
        ttk.Button(btncol, text="Move Down", command=move_down).pack(fill="x")

        steps_tree.bind("<Double-1>", lambda _e: edit_step())
        render_steps()

        bottom = ttk.Frame(dlg)
        bottom.pack(fill="x", padx=12, pady=(0, 12))

        def validate_and_apply():
            combo_text = combo_var.get().strip()
            if not combo_text:
                messagebox.showerror("Missing Combo", "Click Listen Combo, press buttons, release.")
                return

            combo = [c.strip() for c in combo_text.split("+") if c.strip()]
            if not combo:
                messagebox.showerror("Invalid Combo", "Combo is empty.")
                return

            try:
                hold_s = float(hold_var.get().strip())
                if hold_s < 0:
                    hold_s = 0.0
            except Exception:
                hold_s = 0.0

            if not steps:
                messagebox.showerror("Missing Steps", "Add at least one step (Run or Wait).")
                return

            # Validate actions exist + required params present
            for i, s in enumerate(steps, start=1):
                if str(s.get("kind", "run")).lower() == "wait":
                    continue
                aid = str(s.get("action_id", "")).strip()
                action = self.registry.get(aid)
                if not action:
                    messagebox.showerror("Invalid Step", f"Step {i}: unknown action '{aid}'")
                    return
                params = s.get("params", {})
                if not isinstance(params, dict):
                    params = {}
                ok, err = self._validate_params(action.schema, params)
                if not ok:
                    messagebox.showerror("Invalid Step", f"Step {i}: {err}")
                    return

            allowed_controllers = [i for i, var in enumerate(controller_vars) if var.get()]
            if not allowed_controllers:
                messagebox.showerror("Missing Controllers", "Select at least one controller that can run this macro.")
                return

            if mode == "add":
                self.engine.add_macro(combo=combo, hold_seconds=hold_s, active=active_var.get(), steps=steps, allowed_controllers=allowed_controllers)
                self.refresh()
                dlg.destroy()
                return

            ok = self.engine.update_macro(macro_id=macro_id, combo=combo, hold_seconds=hold_s, active=active_var.get(), steps=steps, allowed_controllers=allowed_controllers)
            if not ok:
                messagebox.showerror("Edit Macro", "That change would create a duplicate macro.")
                return

            self.refresh()
            dlg.destroy()

        def cancel():
            if listening["on"]:
                self.cm.cancel_listen()
            dlg.destroy()

        dlg.protocol("WM_DELETE_WINDOW", cancel)
        ttk.Button(bottom, text="Save" if mode == "edit" else "Add", command=validate_and_apply).pack(side="right", padx=(6, 0))
        ttk.Button(bottom, text="Cancel", command=cancel).pack(side="right")


class AppUI:
    def __init__(self, root, macro_engine, controller_manager, registry, logger=None, startup_options=None, on_toggle_start_with_windows=None, on_toggle_start_minimized=None, on_exit_app=None):
        self.root = root
        self.engine = macro_engine
        self.cm = controller_manager
        self.registry = registry
        self.logger = logger
        self._log_win = None
        startup_options = startup_options or {}
        self._on_toggle_start_with_windows = on_toggle_start_with_windows
        self._on_toggle_start_minimized = on_toggle_start_minimized
        self._on_exit_app = on_exit_app
        self._start_with_windows_var = tk.BooleanVar(value=bool(startup_options.get("start_with_windows", False)))
        self._start_minimized_var = tk.BooleanVar(value=bool(startup_options.get("start_minimized", False)))

        self.root.title("Controller Macro Runner")
        self.root.geometry("950x820")

        menubar = tk.Menu(self.root)

        options_menu = tk.Menu(menubar, tearoff=0)
        options_menu.add_checkbutton(
            label="Start with Windows",
            variable=self._start_with_windows_var,
            command=self._toggle_start_with_windows
        )
        options_menu.add_checkbutton(
            label="Start Minimized",
            variable=self._start_minimized_var,
            command=self._toggle_start_minimized
        )
        options_menu.add_separator()
        options_menu.add_command(label="Exit", command=self._exit_app)
        menubar.add_cascade(label="Options", menu=options_menu)

        debug_menu = tk.Menu(menubar, tearoff=0)
        debug_menu.add_command(label="Activity Log", command=self.show_activity_log)
        menubar.add_cascade(label="Debug", menu=debug_menu)
        self.root.config(menu=menubar)

        top_container = ttk.Frame(self.root)
        top_container.pack(fill="x", padx=10, pady=10)
        # Keep the Controller Monitor tall even when its inner content is centered
        top_container.pack_propagate(False)
        top_container.configure(height=580)

        self.monitor = ControllerMonitor(top_container, self.cm)
        self.monitor.pack(fill="both", expand=True)


        self.macros = MacroPanel(self.root, self.engine, self.cm, registry=self.registry)
        self.macros.pack(fill="both", expand=True, padx=10, pady=10)

        self._tick()

    def _toggle_start_with_windows(self):
        enabled = bool(self._start_with_windows_var.get())
        if not callable(self._on_toggle_start_with_windows):
            return

        ok, msg = self._on_toggle_start_with_windows(enabled)
        if not ok:
            self._start_with_windows_var.set(not enabled)
            messagebox.showerror("Start with Windows", msg)

    def _toggle_start_minimized(self):
        enabled = bool(self._start_minimized_var.get())
        if not callable(self._on_toggle_start_minimized):
            return

        ok, msg = self._on_toggle_start_minimized(enabled)
        if not ok:
            self._start_minimized_var.set(not enabled)
            messagebox.showerror("Start Minimized", msg)

    def _exit_app(self):
        if callable(self._on_exit_app):
            self._on_exit_app()
            return
        self.root.destroy()

    def show_activity_log(self):
        if self._log_win and self._log_win.win.winfo_exists():
            self._log_win.win.lift()
            return
        if not self.logger:
            messagebox.showinfo("Activity Log", "Logger not configured.")
            return
        self._log_win = ActivityLogWindow(self.root, self.logger)

    def _tick(self):
        try:
            self.monitor.update_view()
        except Exception:
            pass
        self.root.after(50, self._tick)
