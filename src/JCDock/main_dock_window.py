from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import QMainWindow, QApplication

from .dock_container import DockContainer

if TYPE_CHECKING:
    from .docking_manager import DockingManager

class MainDockWindow(QMainWindow):
    """
    A main application window that provides a central area for docking widgets.
    It serves as a blank slate for the user to add their own menus, toolbars,
    and application logic.
    """
    def __init__(self, manager: DockingManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Docking Application")
        self.setGeometry(300, 300, 800, 600)

        # The central docking area for the main window.
        self.dock_area = DockContainer(manager=self.manager, create_shadow=False, show_title_bar=False)
        self.dock_area.setObjectName("MainDockArea")
        self.dock_area.set_persistent_root(True)  # Mark as persistent root
        self.setCentralWidget(self.dock_area)

        # Set initial margins for the main content area.
        self.centralWidget().layout().setContentsMargins(5, 5, 5, 5)

        # Register the main window and its dock area with the docking manager.
        if self.manager:
            self.manager.register_dock_area(self.dock_area)
            self.manager.set_main_window(self)

        # Install an event filter to manage window stacking order.
        self.installEventFilter(self)

    def closeEvent(self, event):
        """
        Ensure the manager cleans up references when the window is closed.
        """
        if self.manager:
            self.manager.unregister_dock_area(self.dock_area)
        QApplication.instance().quit()
        super().closeEvent(event)

    def eventFilter(self, watched, event):
        """
        Filters events to correctly manage the stacking order of floating windows
        relative to the main window.
        """
        if watched is self:
            # When the window frame is clicked, ensure all floating panels are raised.
            if event.type() == QEvent.Type.NonClientAreaMouseButtonPress:
                if self.manager:
                    self.manager.raise_all_floating_widgets()
                return super().eventFilter(watched, event)


        return super().eventFilter(watched, event)