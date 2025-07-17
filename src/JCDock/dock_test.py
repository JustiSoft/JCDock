import re
import sys
import random
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem
from PySide6.QtCore import Qt, QObject, QEvent, Slot
from PySide6.QtGui import QColor

from docking_manager import DockingManager
from dockable_widget import DockableWidget
from main_dock_window import MainDockWindow


class EventListener(QObject):
    @Slot(object, object)
    def on_widget_docked(self, widget, container):
        container_name = container.windowTitle()
        if container.objectName() == "MainDockArea":
            container_name = "Main Dock Area"
        print(f"--- SIGNAL[widget_docked]: '{widget.windowTitle()}' was docked into '{container_name}' ---")

    @Slot(object)
    def on_widget_undocked(self, widget):
        print(f"--- SIGNAL[widget_undocked]: '{widget.windowTitle()}' became a floating window ---")

    @Slot(str)
    def on_widget_closed(self, persistent_id):
        print(f"--- SIGNAL[widget_closed]: Widget with ID '{persistent_id}' was closed ---")

    @Slot()
    def on_layout_changed(self):
        print("--- SIGNAL[layout_changed]: The dock layout was modified. ---")

class DockingTestApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Docking Library Test")

        # Install the debug event filter on the application instance.
        self.docking_manager = DockingManager()
        # Register our application's factory with the manager.
        self.docking_manager.set_widget_factory(self.app_widget_factory)

        # Create and connect the event listener
        self.event_listener = EventListener()
        self.docking_manager.signals.widget_docked.connect(self.event_listener.on_widget_docked)
        self.docking_manager.signals.widget_undocked.connect(self.event_listener.on_widget_undocked)
        self.docking_manager.signals.widget_closed.connect(self.event_listener.on_widget_closed)
        self.docking_manager.signals.layout_changed.connect(self.event_listener.on_layout_changed)

        self.widget_count = 0

        # Create the main window.
        self.main_window = MainDockWindow(manager=self.docking_manager)
        self.main_window.new_widget_requested.connect(self.create_and_register_new_widget)
        self.main_window.find_widget_test_requested.connect(self.run_find_widget_test)
        self.main_window.list_all_widgets_requested.connect(self.run_list_all_widgets_test)
        self.main_window.list_floating_widgets_requested.connect(self.run_get_floating_widgets_test)
        self.main_window.check_widget_docked_requested.connect(self.run_is_widget_docked_test)
        self.main_window.programmatic_dock_requested.connect(self.run_programmatic_dock_test)
        self.main_window.programmatic_undock_requested.connect(self.run_programmatic_undock_test)
        self.main_window.programmatic_move_requested.connect(self.run_programmatic_move_test)
        self.main_window.activate_widget_requested.connect(self.run_activate_widget_test)

    def _create_test_content(self, name: str) -> QWidget:
        """Creates a simple colored widget with a label for demonstration."""
        content_widget = QWidget()
        bg_color = QColor(random.randint(50, 220), random.randint(50, 220), random.randint(50, 220))

        p = content_widget.palette()
        p.setColor(content_widget.backgroundRole(), bg_color)
        content_widget.setPalette(p)
        content_widget.setAutoFillBackground(True)

        content_layout = QVBoxLayout(content_widget)
        label = QLabel(name)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 24px; background: transparent;")
        content_layout.addWidget(label)

        return content_widget

    def create_and_register_new_widget(self):
        """This application-level function creates a widget and registers it with the manager."""
        self.widget_count += 1
        widget_name = f"Widget {self.widget_count}"
        persistent_id = f"test_widget_{self.widget_count}"

        new_dockable_widget = self._create_and_configure_widget(widget_name, persistent_id)

        self.docking_manager.register_widget(new_dockable_widget)
        new_dockable_widget.show()

    def _create_and_configure_widget(self, name: str, persistent_id: str) -> DockableWidget:
        """Helper method that creates and a single dockable widget."""

        # The color is now passed directly to the constructor.
        # The two-step process of creating then setting is no longer needed.
        new_dockable_widget = DockableWidget(
            name,
            parent=None,
            manager=self.docking_manager,
            persistent_id=persistent_id
        )

        test_content = self._create_test_content(name)
        new_dockable_widget.setContent(test_content, margin_size=5)

        return new_dockable_widget

    def app_widget_factory(self, persistent_id: str) -> DockableWidget:
        """
        This is the application's factory. The docking manager will call this
        during a 'load' operation to recreate a widget from its saved ID.
        """
        print(f"Factory called to create widget with ID: {persistent_id}")
        # In a real app, you might parse the ID to determine widget type and initial state.
        # For example, if persistent_id was "text_editor:/path/to/file.txt"

        # For this test, we'll just extract the count from the ID.
        match = re.search(r'\d+$', persistent_id)
        widget_num = match.group(0) if match else "N/A"
        widget_name = f"Widget {widget_num}"

        return self._create_and_configure_widget(widget_name, persistent_id)

    def run_find_widget_test(self):
        """
        Tests the manager's find_widget_by_id method.
        """
        target_id = "test_widget_2"
        print(f"\n--- RUNNING TEST: Find widget with ID: '{target_id}' ---")

        found_widget = self.docking_manager.find_widget_by_id(target_id)

        if found_widget:
            print(f"SUCCESS: Found widget: {found_widget.windowTitle()}")
            # For visual confirmation, let's change its title and title bar color.
            if "(Found!)" not in found_widget.windowTitle():
                found_widget.set_title(f"{found_widget.windowTitle()} (Found!)")
            found_widget.set_title_bar_color(QColor("#DDA0DD"))  # Plum color
            found_widget.on_activation_request()  # Bring it to the front
        else:
            print(f"FAILURE: Could not find widget with ID: '{target_id}'")

    def run_list_all_widgets_test(self):
        """
        Tests the manager's get_all_widgets method.
        """
        print("\n--- RUNNING TEST: List all widgets ---")
        all_widgets = self.docking_manager.get_all_widgets()

        if not all_widgets:
            print("FAILURE: No widgets returned.")
            return

        print(f"SUCCESS: Found {len(all_widgets)} widgets:")
        for i, widget in enumerate(all_widgets):
            print(f"  {i + 1}: {widget.windowTitle()} (ID: {widget.persistent_id})")
            # Add a prefix to show the test worked visually
            if "(Listed)" not in widget.windowTitle():
                widget.set_title(f"(Listed) {widget.windowTitle()}")
        print("--------------------------------------")

    def run_get_floating_widgets_test(self):
        """
        Tests the manager's get_floating_widgets method.
        """
        print("\n--- RUNNING TEST: Highlight floating widgets ---")
        floating_widgets = self.docking_manager.get_floating_widgets()

        if not floating_widgets:
            print("No floating widgets found.")
        else:
            print(f"SUCCESS: Found {len(floating_widgets)} floating widgets:")
            for i, widget in enumerate(floating_widgets):
                print(f"  {i + 1}: {widget.windowTitle()}")
                # Visually confirm by changing the title bar color
                widget.set_title_bar_color(QColor("#90EE90"))  # Light Green

        print("--------------------------------------------")

    def run_is_widget_docked_test(self):
        """
        Tests the manager's is_widget_docked method.
        """
        target_id = "test_widget_1"
        print(f"\n--- RUNNING TEST: Check if '{target_id}' is docked ---")
        widget_to_check = self.docking_manager.find_widget_by_id(target_id)

        if not widget_to_check:
            print(f"FAILURE: Cannot find '{target_id}' to perform test.")
            return

        is_docked = self.docking_manager.is_widget_docked(widget_to_check)
        print(f"SUCCESS: Is '{widget_to_check.windowTitle()}' docked? -> {is_docked}")
        print("-------------------------------------------------")

    def run_programmatic_dock_test(self):
        """
        Tests programmatically docking one widget into another.
        """
        source_id = "test_widget_1"
        target_id = "test_widget_2"
        print(f"\n--- RUNNING TEST: Programmatically dock '{source_id}' into '{target_id}' ---")

        source_widget = self.docking_manager.find_widget_by_id(source_id)
        target_widget = self.docking_manager.find_widget_by_id(target_id)

        if not source_widget:
            print(f"FAILURE: Cannot find source widget '{source_id}'.")
            return
        if not target_widget:
            print(f"FAILURE: Cannot find target widget '{target_id}'.")
            return

        print(f"SUCCESS: Found widgets. Attempting to dock...")
        self.docking_manager.dock_widget(source_widget, target_widget, "center")
        print("-----------------------------------------------------------------")

    def run_programmatic_undock_test(self):
        """
        Tests programmatically undocking a widget.
        """
        source_id = "test_widget_3"
        target_container = self.main_window.dock_area
        print(f"\n--- RUNNING TEST: Programmatically undock '{source_id}' ---")

        source_widget = self.docking_manager.find_widget_by_id(source_id)
        if not source_widget:
            print(f"FAILURE: Cannot find source widget '{source_id}'.")
            return

        # First, ensure the widget is docked so we can test undocking it.
        if not self.docking_manager.is_widget_docked(source_widget):
            print("INFO: Docking widget into main window first to prepare for test...")
            self.docking_manager.dock_widget(source_widget, target_container, "center")

        # Now, perform the actual test
        print(f"SUCCESS: Found and docked widget. Attempting to undock...")
        self.docking_manager.undock_widget(source_widget)
        print("-------------------------------------------------------------------")

    def run_programmatic_move_test(self):
        """
        Tests programmatically moving a widget to a different container.
        """
        source_id = "test_widget_1"
        target_container = self.main_window.dock_area
        print(f"\n--- RUNNING TEST: Programmatically move '{source_id}' to the main window ---")

        source_widget = self.docking_manager.find_widget_by_id(source_id)
        if not source_widget:
            print(f"FAILURE: Cannot find source widget '{source_id}'.")
            return

        # To make the test obvious, undock it first if it's already docked.
        if self.docking_manager.is_widget_docked(source_widget):
            self.docking_manager.undock_widget(source_widget)

        print(f"SUCCESS: Found widget. Attempting to move...")
        self.docking_manager.move_widget_to_container(source_widget, target_container)
        print("--------------------------------------------------------------------------")

    def run_activate_widget_test(self):
        """
        Tests the manager's activate_widget method.
        """
        id_to_activate = "test_widget_1"
        id_to_dock_with = "test_widget_2"
        print(f"\n--- RUNNING TEST: Activate '{id_to_activate}' ---")

        widget_to_activate = self.docking_manager.find_widget_by_id(id_to_activate)
        widget_to_dock_with = self.docking_manager.find_widget_by_id(id_to_dock_with)

        if not widget_to_activate or not widget_to_dock_with:
            print(f"FAILURE: Could not find necessary widgets for test.")
            return

        # 1. Setup: Ensure the widgets are tabbed together in the main window.
        if not self.docking_manager.is_widget_docked(widget_to_dock_with):
            self.docking_manager.move_widget_to_container(widget_to_dock_with, self.main_window.dock_area)
        if not self.docking_manager.is_widget_docked(widget_to_activate):
            self.docking_manager.move_widget_to_container(widget_to_activate, self.main_window.dock_area)

        # 2. Setup: Ensure the *other* widget is the active one to start.
        self.docking_manager.activate_widget(widget_to_dock_with)

        # 3. Run Test: Now, activate the target widget.
        print(f"INFO: State is set up. Activating '{widget_to_activate.windowTitle()}'...")
        self.docking_manager.activate_widget(widget_to_activate)
        print(f"SUCCESS: activate_widget called for '{widget_to_activate.windowTitle()}'.")
        print("-------------------------------------------------")


    def run(self):
        """Shows the main window and starts the application."""
        self.main_window.show()
        self.create_and_register_new_widget()
        self.create_and_register_new_widget()
        self.create_and_register_new_widget()
        sys.exit(self.app.exec())

if __name__ == "__main__":
    test_app = DockingTestApp()
    test_app.run()
