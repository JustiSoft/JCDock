from enum import Enum

class DockingState(Enum):
    """Operational states for the DockingManager state machine."""
    IDLE = "idle"
    RENDERING = "rendering"
    DRAGGING_WINDOW = "dragging_window"
    RESIZING_WINDOW = "resizing_window"
    DRAGGING_TAB = "dragging_tab"