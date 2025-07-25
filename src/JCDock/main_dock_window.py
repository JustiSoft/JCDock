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

        self.dock_area = DockContainer(manager=self.manager, create_shadow=False, show_title_bar=False)
        self.dock_area.setObjectName("MainDockArea")
        self.dock_area.set_persistent_root(True)
        self.setCentralWidget(self.dock_area)

        self.centralWidget().layout().setContentsMargins(5, 5, 5, 5)

        if self.manager:
            self.manager.register_dock_area(self.dock_area)
            self.manager.set_main_window(self)

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
        Filters events for the main window.
        """  
        return super().eventFilter(watched, event)