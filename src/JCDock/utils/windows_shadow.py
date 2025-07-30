import sys
import ctypes
from ctypes import wintypes

def apply_native_shadow(widget):
    """
    Apply native Windows shadow to a QWidget using DWM API.
    
    Args:
        widget: QWidget instance to apply shadow to
        
    Returns:
        bool: True if shadow was applied successfully, False otherwise
    """
    # Only apply on Windows platform
    if sys.platform != "win32":
        return False
    
    try:
        # Load the required DLL
        dwmapi = ctypes.WinDLL("dwmapi")
        
        # Define the MARGINS struct that wintypes is missing
        class MARGINS(ctypes.Structure):
            _fields_ = [
                ("cxLeftWidth", ctypes.c_int),
                ("cxRightWidth", ctypes.c_int),
                ("cyTopHeight", ctypes.c_int),
                ("cyBottomHeight", ctypes.c_int),
            ]
        
        # Define constants for DWM attributes
        DWMWA_NCRENDERING_POLICY = 2
        DWMNCRP_ENABLED = 2
        
        # Get the window handle (HWND)
        hwnd = widget.winId()
        
        # Enable DWM non-client area rendering. This tells DWM to take over
        # drawing the border and shadow.
        policy = wintypes.DWORD(DWMNCRP_ENABLED)
        dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            wintypes.DWORD(DWMWA_NCRENDERING_POLICY),
            ctypes.byref(policy),
            ctypes.sizeof(policy)
        )
        
        # Extend the frame into the client area.
        # A value of -1 for the margins tells DWM to use the default system margins,
        # creating the standard "Aero" shadow effect.
        margins = MARGINS(-1, -1, -1, -1)
        dwmapi.DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd), ctypes.byref(margins))
        
        return True
        
    except Exception as e:
        # Silently fail on non-Windows systems or if DWM is not available
        return False