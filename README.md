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

🕹 Controller Backends

Controller Commander now supports both major Windows controller paths:

- **XInput** (`xinput*.dll`) for Xbox-compatible controllers
- **DirectInput / RawInput-style** devices via **pygame joystick polling** and **inputs** gamepad events, plus native **WinMM joystick** polling (commonly includes many Bluetooth controllers)
- Optional HID enumeration support through `hid` for diagnostics

This means many controllers that do not appear through XInput can still be detected and used for macro triggers.

🖥 Platform

Windows

Python (Tkinter UI)

HID / controller input libraries
