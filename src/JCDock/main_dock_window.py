from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QTimer, Signal
from PySide6.QtWidgets import QMainWindow, QMenuBar, QApplication
from PySide6.QtGui import QAction

from dock_container import DockContainer

# This block is only processed by type checkers, not at runtime.
if TYPE_CHECKING:
    from docking_manager import DockingManager
    from dock_test import DockingTestApp


class MainDockWindow(QMainWindow):
    """
    A main application window that provides a central area for docking widgets.
    It can have its own menus and toolbars, separate from the docking area.
    """
    new_widget_requested = Signal()
    find_widget_test_requested = Signal()
    list_all_widgets_requested = Signal()
    list_floating_widgets_requested = Signal()
    check_widget_docked_requested = Signal()
    programmatic_dock_requested = Signal()
    programmatic_undock_requested = Signal()
    programmatic_move_requested = Signal()
    activate_widget_requested = Signal()

    def __init__(self, manager: 'DockingManager', parent=None):
        super().__init__(parent)
        self.manager = manager
        # The dependency on app_logic has been removed.
        # self.app_logic = app_logic
        self.setWindowTitle("Docking Application")
        self.setGeometry(300, 300, 800, 600)
        self.last_saved_layout = None
        self._create_menu_bar()

        self.dock_area = DockContainer(manager=self.manager, create_shadow=False, show_title_bar=False)
        self.dock_area.setObjectName("MainDockArea")
        self.setCentralWidget(self.dock_area)

        self.centralWidget().layout().setContentsMargins(5, 5, 5, 5)

        if self.manager:
            self.manager.register_dock_area(self.dock_area)
            self.manager.set_main_window(self)

        self.installEventFilter(self)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        # The "New Widget" action, which emits a signal for the application to handle.
        new_widget_action = QAction("New Widget", self)
        new_widget_action.triggered.connect(self.new_widget_requested.emit)
        file_menu.addAction(new_widget_action)

        # The "New Floating Dock Area" action, which calls a method on the manager.
        new_floating_root_action = QAction("New Floating Dock Area", self)
        if self.manager:
            new_floating_root_action.triggered.connect(self.manager.create_new_floating_root)
        file_menu.addAction(new_floating_root_action)

        file_menu.addSeparator()

        save_layout_action = QAction("Save Layout", self)
        save_layout_action.triggered.connect(self.save_layout)
        file_menu.addAction(save_layout_action)

        # Add the "Load Layout" action
        load_layout_action = QAction("Load Layout", self)
        load_layout_action.triggered.connect(self.load_layout)
        file_menu.addAction(load_layout_action)

        file_menu.addSeparator()

        list_all_action = QAction("List All Widgets", self)
        list_all_action.triggered.connect(self.list_all_widgets_requested.emit)
        file_menu.addAction(list_all_action)

        list_floating_action = QAction("Highlight Floating Widgets", self)
        list_floating_action.triggered.connect(self.list_floating_widgets_requested.emit)
        file_menu.addAction(list_floating_action)

        check_docked_action = QAction("Check if 'Widget 1' is Docked", self)
        check_docked_action.triggered.connect(self.check_widget_docked_requested.emit)
        file_menu.addAction(check_docked_action)

        file_menu.addSeparator()

        prog_dock_action = QAction("Dock Widget 1 into 2 (Center)", self)
        prog_dock_action.triggered.connect(self.programmatic_dock_requested.emit)
        file_menu.addAction(prog_dock_action)

        prog_undock_action = QAction("Undock 'Widget 3'", self)
        prog_undock_action.triggered.connect(self.programmatic_undock_requested.emit)
        file_menu.addAction(prog_undock_action)

        prog_move_action = QAction("Move 'Widget 1' to Main Window", self)
        prog_move_action.triggered.connect(self.programmatic_move_requested.emit)
        file_menu.addAction(prog_move_action)

        file_menu.addSeparator()

        # Menu for final category
        view_menu = menu_bar.addMenu("View")
        find_widget_action = QAction("Find & Highlight 'Widget 2'", self)
        find_widget_action.triggered.connect(self.find_widget_test_requested.emit)
        view_menu.addAction(find_widget_action)

        activate_widget_action = QAction("Activate 'Widget 1'", self)
        activate_widget_action.triggered.connect(self.activate_widget_requested.emit)
        view_menu.addAction(activate_widget_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(QApplication.instance().quit)
        file_menu.addAction(exit_action)

    def save_layout(self):
        """
        Called when the user clicks the "Save Layout" menu item.
        """
        if not self.manager:
            return

        try:
            # Store the layout in our instance variable for the load button to use
            self.last_saved_layout = self.manager.save_layout_to_bytearray()
            print("\n--- LAYOUT SAVED ---\n")
        except Exception as e:
            print(f"Error saving layout: {e}")

    def load_layout(self):
        """
        Called when the user clicks the "Load Layout" menu item.
        """
        if not self.manager:
            return

        if self.last_saved_layout:
            print("\n--- LOADING LAYOUT ---\n")
            self.manager.load_layout_from_bytearray(self.last_saved_layout)
        else:
            print("No layout has been saved yet.")

    def closeEvent(self, event):
        """
        Ensure the manager cleans up references and the app closes properly.
        """
        if self.manager:
            self.manager.unregister_dock_area(self.dock_area)
        QApplication.instance().quit()
        super().closeEvent(event)

    def eventFilter(self, watched, event):
        # We only care about events for the MainDockWindow itself.
        if watched is self:
            # Case 1: The title bar (or any non-client frame part) is clicked.
            # This event is very specific and gives us an early hook to apply our logic
            # before the OS might override it.
            if event.type() == QEvent.Type.NonClientAreaMouseButtonPress:
                if self.manager:
                    self.manager.raise_all_floating_widgets()
                return super().eventFilter(watched, event)

            # Case 2: The window is activated by other means (e.g., clicking the client area, taskbar).
            # This is a more general event. We use the timer to ensure our fix
            # runs *after* the OS has completed its default activation/raising process.
            if event.type() == QEvent.Type.WindowActivate:
                if self.manager:
                    QTimer.singleShot(0, self.manager.raise_all_floating_widgets)
                return super().eventFilter(watched, event)

        return super().eventFilter(watched, event)

