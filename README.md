📘 Controller Commander

Controller Commander is a Windows desktop application that allows users to create and execute customizable macros triggered by game controller button combinations. It provides real-time controller monitoring, flexible macro workflows, and plugin extensibility, all accessible through a system tray–based interface.

The application is designed for reliability, responsiveness, and ease of configuration, supporting multiple controllers and complex action sequences.

🚀 Key Features
🎮 Real-Time Controller Monitoring

Visual representation of controller inputs (buttons, triggers, analog sticks)

Multi-controller support with selectable active device

Live connection status updates


⚙️ Macro System

Trigger macros using button combinations or hold durations

Sequential step execution with configurable timing

Support for actions such as:

Executables / scripts

Delays

URL launching

Plugin actions

🔌 Plugin Architecture

Extensible action system via plugin loader

Custom macro steps can be added without modifying core code

🧠 Execution Engine

Dedicated macro execution engine with timing control

Conflict handling between simultaneous triggers

Reliable background processing

📋 Macro Management UI

Editable macro list with activation toggles

Context menu for add/edit/delete operations

Scrollable interface for large macro collections

🗂 Profile Management

Persistent macro profiles

Structured storage for user configurations

🪟 System Tray Integration

Minimize-to-tray behavior

Background operation without occupying taskbar space

Auto-generated tray icon if missing

Quick access to settings and exit controls

📊 Logging & Diagnostics

Activity logging

Debug log for tray and runtime behavior

Error visibility for troubleshooting

🏗 Architecture Overview

The project is organized into modular components:

controller_manager — Hardware input detection and polling

macro_engine — Macro trigger evaluation

execution_engine — Step execution runtime

profile_manager — Configuration persistence

plugin_loader — Extensible action system

action_registry — Available action definitions

activity_logger / logger — Logging infrastructure

ui — Tkinter-based user interface

tray — System tray lifecycle management

main — Application bootstrap and orchestration

## Building a Windows `.exe` (all dependencies included)

### 1) Install build tooling and runtime deps

Use a fresh virtual environment on Windows, then install your dependencies plus PyInstaller.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install pyinstaller pillow pystray pywin32
```

> If your local code uses additional libraries, install those too before building.

### 2) Build from `main.py` (entry point)

`main.py` is the file you convert into an executable. The other `.py` files are imported as modules and bundled automatically when they are statically imported.

```powershell
pyinstaller --noconfirm --clean --windowed --name ControllerCommander `
  --add-data "plugins;plugins" `
  --add-data "profiles;profiles" `
  --hidden-import win32api --hidden-import win32con --hidden-import win32gui `
  main.py
```

This creates:

- `dist\ControllerCommander\ControllerCommander.exe` (default folder build)
- Or use `--onefile` if you want a single exe file.

### 3) Why include `plugins` and `profiles`

- `plugins/` is scanned at runtime, so plugin `.py` files are **not** discovered purely by static imports.
- `profiles/` contains default settings/profile JSON files the app expects.

If those folders are missing in the packaged app, plugin actions and defaults may not load.

### 4) Plugin dependencies

Each plugin can have its own Python/import requirements. Those are not "magic"; they must be installed at build time so PyInstaller can bundle them.

- If a plugin only uses stdlib + already installed packages, nothing extra is needed.
- If a plugin imports extra packages, install them and (if needed) add `--hidden-import` entries.

### 5) How files complement the app

- `main.py`: startup/orchestration, built-in action registration, loads plugins, creates UI/tray, starts controller polling.
- `plugin_loader.py`: dynamically loads `plugins/*.py` and calls each plugin's `register(registry)`.
- `macro_engine.py` + `execution_engine.py`: evaluate triggers and execute macro steps.
- `ui.py`: Tkinter editor/monitor.
- `tray.py`: system tray behavior (native win32 when available, fallback to `pystray`).
- `profiles/*.json`: persisted macro/app settings.

### 6) One practical packaging tip

`startup_manager.py` currently uses `script_path=__file__` from `main.py`. For packaged apps, you may want to adapt startup registration to point at `sys.executable` when frozen so "Start with Windows" launches the exe directly.

🎯 Use Cases

Game automation

Accessibility workflows

Productivity shortcuts via controller

Streaming / content creation triggers

Testing and QA automation

Custom hardware integrations

🔒 Design Goals

Lightweight background operation

High input responsiveness

Modular extensibility

Clear separation of UI and logic

Stable long-running behavior

🖥 Platform

Windows

Python (Tkinter UI)

HID / controller input libraries
