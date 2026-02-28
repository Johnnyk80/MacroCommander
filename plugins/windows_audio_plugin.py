"""
Windows Audio Plugin for Macro Commander / Macro Runner.

Provides one macro action that can:
- Scan and list active playback devices.
- Switch the default playback device.
- Set the master volume for that target device.

This plugin is Windows-only.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
from typing import Any, Dict, List


AUDIO_BRIDGE_PS = r"""
$ErrorActionPreference = 'Stop'

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class AudioBridge
{
    public static string ListRenderDevicesJson()
    {
        var items = new List<string>();
        var e = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
        IMMDeviceCollection coll;
        Marshal.ThrowExceptionForHR(e.EnumAudioEndpoints((int)EDataFlow.eRender, DeviceState.ACTIVE, out coll));

        uint count;
        Marshal.ThrowExceptionForHR(coll.GetCount(out count));
        for (uint i = 0; i < count; i++)
        {
            IMMDevice dev;
            Marshal.ThrowExceptionForHR(coll.Item(i, out dev));

            string id;
            Marshal.ThrowExceptionForHR(dev.GetId(out id));

            IPropertyStore store;
            Marshal.ThrowExceptionForHR(dev.OpenPropertyStore(0, out store));

            PROPERTYKEY key = PropertyKeys.PKEY_Device_FriendlyName;
            PROPVARIANT pv;
            Marshal.ThrowExceptionForHR(store.GetValue(ref key, out pv));
            string name = pv.GetValue();
            PropVariantClear(ref pv);

            items.Add("{\"id\":\"" + Escape(id) + "\",\"name\":\"" + Escape(name) + "\"}");
        }

        return "[" + string.Join(",", items.ToArray()) + "]";
    }

    public static void SetDefaultRenderDevice(string deviceId)
    {
        var policy = new PolicyConfigClient() as IPolicyConfig;
        if (policy == null)
            throw new Exception("Unable to create PolicyConfigClient.");

        Marshal.ThrowExceptionForHR(policy.SetDefaultEndpoint(deviceId, ERole.eConsole));
        Marshal.ThrowExceptionForHR(policy.SetDefaultEndpoint(deviceId, ERole.eMultimedia));
        Marshal.ThrowExceptionForHR(policy.SetDefaultEndpoint(deviceId, ERole.eCommunications));
    }

    public static void SetDeviceMasterVolume(string deviceId, float scalar)
    {
        if (scalar < 0f) scalar = 0f;
        if (scalar > 1f) scalar = 1f;

        var e = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
        IMMDevice dev;
        Marshal.ThrowExceptionForHR(e.GetDevice(deviceId, out dev));

        Guid iid = typeof(IAudioEndpointVolume).GUID;
        object obj;
        Marshal.ThrowExceptionForHR(dev.Activate(ref iid, 23, IntPtr.Zero, out obj));

        var ep = (IAudioEndpointVolume)obj;
        Marshal.ThrowExceptionForHR(ep.SetMasterVolumeLevelScalar(scalar, Guid.Empty));
    }

    private static string Escape(string s)
    {
        if (s == null) return "";
        return s.Replace("\\", "\\\\").Replace("\"", "\\\"");
    }

    [DllImport("ole32.dll")]
    private static extern int PropVariantClear(ref PROPVARIANT pvar);

    [ComImport]
    [Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
    private class MMDeviceEnumeratorComObject { }

    [ComImport]
    [Guid("870af99c-171d-4f9e-af0d-e63df40c2bc9")]
    private class PolicyConfigClient { }

    private enum EDataFlow
    {
        eRender = 0,
        eCapture = 1,
        eAll = 2,
        EDataFlow_enum_count = 3
    }

    private static class DeviceState
    {
        public const uint ACTIVE = 0x00000001;
    }

    private enum ERole
    {
        eConsole = 0,
        eMultimedia = 1,
        eCommunications = 2,
        ERole_enum_count = 3
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct PROPERTYKEY
    {
        public Guid fmtid;
        public uint pid;
        public PROPERTYKEY(Guid f, uint p) { fmtid = f; pid = p; }
    }

    private static class PropertyKeys
    {
        public static readonly PROPERTYKEY PKEY_Device_FriendlyName = new PROPERTYKEY(new Guid("a45c254e-df1c-4efd-8020-67d146a850e0"), 14);
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct PROPVARIANT
    {
        public ushort vt;
        public ushort wReserved1;
        public ushort wReserved2;
        public ushort wReserved3;
        public IntPtr p;
        public int p2;

        public string GetValue()
        {
            if (vt == 31 || vt == 30)
            {
                return Marshal.PtrToStringUni(p) ?? "";
            }
            return "";
        }
    }

    [ComImport]
    [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IMMDeviceEnumerator
    {
        int EnumAudioEndpoints(int dataFlow, uint dwStateMask, [MarshalAs(UnmanagedType.Interface)] out IMMDeviceCollection ppDevices);
        int GetDefaultAudioEndpoint(int dataFlow, int role, [MarshalAs(UnmanagedType.Interface)] out IMMDevice ppEndpoint);
        int GetDevice([MarshalAs(UnmanagedType.LPWStr)] string pwstrId, out IMMDevice ppDevice);
        int RegisterEndpointNotificationCallback(IntPtr pClient);
        int UnregisterEndpointNotificationCallback(IntPtr pClient);
    }

    [ComImport]
    [Guid("0BD7A1BE-7A1A-44DB-8397-C0A1D6B59D61")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IMMDeviceCollection
    {
        int GetCount(out uint pcDevices);
        int Item(uint nDevice, [MarshalAs(UnmanagedType.Interface)] out IMMDevice ppDevice);
    }

    [ComImport]
    [Guid("D666063F-1587-4E43-81F1-B948E807363F")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IMMDevice
    {
        int Activate(ref Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
        int OpenPropertyStore(int stgmAccess, out IPropertyStore ppProperties);
        int GetId([MarshalAs(UnmanagedType.LPWStr)] out string ppstrId);
        int GetState(out int pdwState);
    }

    [ComImport]
    [Guid("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IPropertyStore
    {
        int GetCount(out uint cProps);
        int GetAt(uint iProp, out PROPERTYKEY pkey);
        int GetValue(ref PROPERTYKEY key, out PROPVARIANT pv);
        int SetValue(ref PROPERTYKEY key, ref PROPVARIANT propvar);
        int Commit();
    }

    [ComImport]
    [Guid("f8679f50-850a-41cf-9c72-430f290290c8")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IPolicyConfig
    {
        int GetMixFormat();
        int GetDeviceFormat();
        int ResetDeviceFormat();
        int SetDeviceFormat();
        int GetProcessingPeriod();
        int SetProcessingPeriod();
        int GetShareMode();
        int SetShareMode();
        int GetPropertyValue();
        int SetPropertyValue();
        int SetDefaultEndpoint([MarshalAs(UnmanagedType.LPWStr)] string wszDeviceId, ERole eRole);
        int SetEndpointVisibility();
    }

    [ComImport]
    [Guid("5CDF2C82-841E-4546-9722-0CF74078229A")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IAudioEndpointVolume
    {
        int RegisterControlChangeNotify(IntPtr pNotify);
        int UnregisterControlChangeNotify(IntPtr pNotify);
        int GetChannelCount(out uint pnChannelCount);
        int SetMasterVolumeLevel(float fLevelDB, Guid pguidEventContext);
        int SetMasterVolumeLevelScalar(float fLevel, Guid pguidEventContext);
        int GetMasterVolumeLevel(out float pfLevelDB);
        int GetMasterVolumeLevelScalar(out float pfLevel);
        int SetChannelVolumeLevel(uint nChannel, float fLevelDB, Guid pguidEventContext);
        int SetChannelVolumeLevelScalar(uint nChannel, float fLevel, Guid pguidEventContext);
        int GetChannelVolumeLevel(uint nChannel, out float pfLevelDB);
        int GetChannelVolumeLevelScalar(uint nChannel, out float pfLevel);
        int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, Guid pguidEventContext);
        int GetMute(out bool pbMute);
        int GetVolumeStepInfo(out uint pnStep, out uint pnStepCount);
        int VolumeStepUp(Guid pguidEventContext);
        int VolumeStepDown(Guid pguidEventContext);
        int QueryHardwareSupport(out uint pdwHardwareSupportMask);
        int GetVolumeRange(out float pflVolumeMindB, out float pflVolumeMaxdB, out float pflVolumeIncrementdB);
    }
}
"@ | Out-Null

$mode = $env:AUDIO_PLUGIN_MODE

if ($mode -eq 'list') {
    [AudioBridge]::ListRenderDevicesJson()
    exit 0
}

if ($mode -eq 'apply') {
    $deviceId = $env:AUDIO_PLUGIN_DEVICE_ID
    $setDefault = $env:AUDIO_PLUGIN_SET_DEFAULT
    $volumePercent = [double]$env:AUDIO_PLUGIN_VOLUME_PERCENT

    if ($setDefault -eq '1') {
        [AudioBridge]::SetDefaultRenderDevice($deviceId)
    }

    [AudioBridge]::SetDeviceMasterVolume($deviceId, [float]($volumePercent / 100.0))
    'ok'
    exit 0
}

throw 'Unknown AUDIO_PLUGIN_MODE.'
"""


def _run_bridge(mode: str, extra_env: Dict[str, str] | None = None) -> str:
    env = dict(extra_env or {})
    env["AUDIO_PLUGIN_MODE"] = mode

    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            AUDIO_BRIDGE_PS,
        ],
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        check=False,
    )

    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "PowerShell bridge failed.").strip()
        raise RuntimeError(msg)

    return (proc.stdout or "").strip()


def _list_devices() -> List[Dict[str, str]]:
    out = _run_bridge("list")
    devices = json.loads(out) if out else []
    safe: List[Dict[str, str]] = []
    for d in devices:
        if isinstance(d, dict) and d.get("id") and d.get("name"):
            safe.append({"id": str(d["id"]), "name": str(d["name"])})
    return safe


def register(registry):
    is_windows = platform.system().lower() == "windows"

    devices: List[Dict[str, str]] = []
    device_options: List[Dict[str, str]] = []
    description = (
        "Switches default Windows playback device and sets that device master volume. "
        "Scans active output devices when plugin loads."
    )

    if is_windows:
        try:
            devices = _list_devices()
            device_options = [{"label": f"{d['name']} ({d['id']})", "value": d["id"]} for d in devices]
        except Exception as ex:
            description += f" Device scan failed: {ex}"
    else:
        description += " (Unavailable on non-Windows hosts.)"

    def switch_device_and_volume(params: Dict[str, Any]):
        if not is_windows:
            return False, "Windows audio actions are only available on Windows."

        logger = params.get("_logger")

        device_id = str(params.get("device_id", "")).strip()
        if not device_id:
            return False, "Choose a device_id from the scanned list."

        try:
            volume_percent = float(params.get("volume_percent", 50.0))
        except Exception:
            return False, "volume_percent must be a number (0-100)."

        volume_percent = max(0.0, min(100.0, volume_percent))
        set_default = bool(params.get("set_as_default", True))

        try:
            _run_bridge(
                "apply",
                {
                    "AUDIO_PLUGIN_DEVICE_ID": device_id,
                    "AUDIO_PLUGIN_SET_DEFAULT": "1" if set_default else "0",
                    "AUDIO_PLUGIN_VOLUME_PERCENT": str(volume_percent),
                },
            )
        except Exception as ex:
            return False, f"Failed to apply audio settings: {ex}"

        chosen_name = next((d["name"] for d in devices if d["id"] == device_id), device_id)
        msg = f"Audio updated: {chosen_name}, volume {volume_percent:.0f}%"

        if logger:
            try:
                logger.log(f"[WindowsAudioPlugin] {msg}")
            except Exception:
                pass

        return True, msg

    registry.register_action(
        action_id="windows.audio.switch_and_volume",
        name="Windows: Switch Sound Device + Set Volume",
        description=description,
        schema={
            "device_id": {
                "type": "choice",
                "label": "Playback Device",
                "required": True,
                "options": device_options,
            },
            "volume_percent": {
                "type": "float",
                "label": "Volume Percent (0-100)",
                "required": True,
                "default": 50,
            },
            "set_as_default": {
                "type": "bool",
                "label": "Set as default output device",
                "required": False,
                "default": True,
            },
        },
        run=switch_device_and_volume,
    )
