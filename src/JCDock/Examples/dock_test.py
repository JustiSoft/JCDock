import re
import sys
import random
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem
from PySide6.QtCore import Qt, QObject, QEvent, Slot
from PySide6.QtGui import QColor

from JCDock.docking_manager import DockingManager
from JCDock.dockable_widget import DockableWidget
from JCDock.main_dock_window import MainDockWindow


class EventListener(QObject):
    @Slot(object, object)
    def on_widget_docked(self, widget, container):
        container_name = container.windowTitle()
        if container.objectName() == "MainDockArea":
            container_name = "Main Dock Area"


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
        """Creates a simple table with test data for demonstration."""
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)  # Use the full space

        # Create and configure the table
        table_widget = QTableWidget()

        # This stylesheet adds a border to the table body and carefully styles
        # the header sections to create a complete, solid black frame.
        stylesheet = """
            QTableView {
                border: 1px solid black;
                gridline-color: black;
            }
            QTableCornerButton::section {
                background-color: #f0f0f0;
                border-right: 1px solid black;
                border-bottom: 1px solid black;
            }
        """
        table_widget.setStyleSheet(stylesheet)

        table_widget.setRowCount(5)
        table_widget.setColumnCount(3)
        table_widget.setHorizontalHeaderLabels(["Item ID", "Description", "Value"])

        # Populate the table with sample data
        for row in range(5):
            item_id = QTableWidgetItem(f"{name}-I{row+1}")
            item_desc = QTableWidgetItem(f"Sample data item for row {row+1}")
            item_value = QTableWidgetItem(str(random.randint(100, 999)))

            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_value.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            table_widget.setItem(row, 0, item_id)
            table_widget.setItem(row, 1, item_desc)
            table_widget.setItem(row, 2, item_value)

        # Adjust column sizes to fit the content
        table_widget.resizeColumnsToContents()

        # Add the table to the layout
        content_layout.addWidget(table_widget)

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
            if "(Found!)" not in found_widget.windowTitle():
                found_widget.set_title(f"{found_widget.windowTitle()} (Found!)")
            found_widget.set_title_bar_color(QColor("#DDA0DD"))  # Plum color
            found_widget.on_activation_request()
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

        if not self.docking_manager.is_widget_docked(source_widget):
            print("INFO: Docking widget into main window first to prepare for test...")
            self.docking_manager.dock_widget(source_widget, target_container, "center")

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

        if not self.docking_manager.is_widget_docked(widget_to_dock_with):
            self.docking_manager.move_widget_to_container(widget_to_dock_with, self.main_window.dock_area)
        if not self.docking_manager.is_widget_docked(widget_to_activate):
            self.docking_manager.move_widget_to_container(widget_to_activate, self.main_window.dock_area)

        self.docking_manager.activate_widget(widget_to_dock_with)

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