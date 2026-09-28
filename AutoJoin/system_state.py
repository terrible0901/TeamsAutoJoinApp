"""Read-only Windows session checks for fail-safe scheduling."""
from __future__ import annotations

import ctypes
from ctypes import wintypes


def desktop_unlocked() -> bool:
    user32 = ctypes.windll.user32
    user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user32.OpenInputDesktop.restype = wintypes.HANDLE
    user32.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                   wintypes.LPVOID, wintypes.DWORD,
                                                   ctypes.POINTER(wintypes.DWORD)]
    user32.GetUserObjectInformationW.restype = wintypes.BOOL
    user32.CloseDesktop.argtypes = [wintypes.HANDLE]
    user32.CloseDesktop.restype = wintypes.BOOL
    handle = user32.OpenInputDesktop(0, False, 0x0001)  # DESKTOP_READOBJECTS
    if not handle:
        return False
    try:
        name = ctypes.create_unicode_buffer(128)
        needed = wintypes.DWORD(0)
        if not user32.GetUserObjectInformationW(handle, 2, name, ctypes.sizeof(name), ctypes.byref(needed)):
            return False
        return name.value.casefold() == "default"
    finally:
        user32.CloseDesktop(handle)
