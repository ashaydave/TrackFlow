# Runtime hook for PyInstaller — pre-load onnxruntime DLLs and diagnose failures.
import ctypes
import os
import sys

if sys.platform == "win32" and hasattr(sys, "_MEIPASS"):
    _ort_capi = os.path.join(sys._MEIPASS, "onnxruntime", "capi")

    # Write diagnostics to the same log as main.py
    _log_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "TrackFlow")
    os.makedirs(_log_dir, exist_ok=True)
    _log = open(os.path.join(_log_dir, "ort_hook.log"), "w", encoding="utf-8")

    def _log_msg(msg):
        _log.write(msg + "\n")
        _log.flush()

    _log_msg(f"rthook_onnxruntime: _MEIPASS={sys._MEIPASS}")
    _log_msg(f"rthook_onnxruntime: _ort_capi={_ort_capi}")
    _log_msg(f"rthook_onnxruntime: exists={os.path.isdir(_ort_capi)}")

    if os.path.isdir(_ort_capi):
        os.add_dll_directory(_ort_capi)
        os.environ["PATH"] = _ort_capi + os.pathsep + os.environ.get("PATH", "")
        _log_msg("Added _ort_capi to dll dirs and PATH")

        # List files present
        _log_msg(f"Files in capi: {os.listdir(_ort_capi)}")
        _log_msg(f"DLLs in _MEIPASS root: {[f for f in os.listdir(sys._MEIPASS) if f.lower().endswith(('.dll', '.pyd'))]}")

        # Try pre-loading each DLL via ctypes to identify which one fails
        for _dll_name in ["onnxruntime.dll", "onnxruntime_providers_shared.dll", "onnxruntime_pybind11_state.pyd"]:
            _dll_path = os.path.join(_ort_capi, _dll_name)
            try:
                ctypes.CDLL(_dll_path)
                _log_msg(f"ctypes.CDLL({_dll_name}): OK")
            except Exception as _e:
                _log_msg(f"ctypes.CDLL({_dll_name}): FAILED - {type(_e).__name__}: {_e}")

                # Try WinError code for more detail
                err = ctypes.get_last_error()
                _log_msg(f"  GetLastError: {err}")

    _log.close()
