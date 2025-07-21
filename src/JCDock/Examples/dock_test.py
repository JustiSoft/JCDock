import re
import sys
import random
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QMenuBar, QMenu, QStyle, QHBoxLayout
from PySide6.QtCore import Qt, QObject, QEvent, Slot, QSize, QPoint, QRect
from PySide6.QtGui import QColor

from JCDock.docking_manager import DockingManager
from JCDock.dock_panel import DockPanel
from JCDock.main_dock_window import MainDockWindow
from JCDock.dock_container import DockContainer


class EventListener(QObject):
    """
    A simple event listener to demonstrate connecting to DockingManager signals.
    """
    @Slot(object, object)
    def on_widget_docked(self, widget, container):
        container_name = container.windowTitle()
        if container.objectName() == "MainDockArea":
            container_name = "Main Dock Area"
        print(f"--- SIGNAL[widget_docked]: '{widget.windowTitle()}' docked into '{container_name}' ---")

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
    """
    Main application class for testing the JCDock library.
    Sets up the main window, docking manager, and test functions.
    """
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Docking Library Test")

        self.docking_manager = DockingManager()
        self.docking_manager.set_widget_factory(self.app_widget_factory)

        self.event_listener = EventListener()
        self.docking_manager.signals.widget_docked.connect(self.event_listener.on_widget_docked)
        self.docking_manager.signals.widget_undocked.connect(self.event_listener.on_widget_undocked)
        self.docking_manager.signals.widget_closed.connect(self.event_listener.on_widget_closed)
        self.docking_manager.signals.layout_changed.connect(self.event_listener.on_layout_changed)

        self.widget_count = 0
        self.main_window = MainDockWindow(manager=self.docking_manager)

        self.saved_layout_data = None

        self._create_test_menu_bar()

    def _create_test_menu_bar(self):
        """
        Creates the menu bar for the main window with various test actions.
        """
        menu_bar = self.main_window.menuBar()

        file_menu = menu_bar.addMenu("File")
        save_layout_action = file_menu.addAction("Save Layout")
        save_layout_action.triggered.connect(self.save_layout)
        load_layout_action = file_menu.addAction("Load Layout")
        load_layout_action.triggered.connect(self.load_layout)
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.main_window.close)

        widget_menu = menu_bar.addMenu("Widgets")
        new_widget_action = widget_menu.addAction("Create New Widget")
        new_widget_action.triggered.connect(self.create_and_register_new_widget)
        create_floating_root_action = widget_menu.addAction("Create New Floating Root")
        create_floating_root_action.triggered.connect(self.docking_manager.create_new_floating_root)

        test_menu = menu_bar.addMenu("Tests")

        find_widget_action = test_menu.addAction("Test: Find Widget by ID")
        find_widget_action.triggered.connect(self.run_find_widget_test)

        list_all_widgets_action = test_menu.addAction("Test: List All Widgets")
        list_all_widgets_action.triggered.connect(self.run_list_all_widgets_test)

        list_floating_widgets_action = test_menu.addAction("Test: List Floating Widgets")
        list_floating_widgets_action.triggered.connect(self.run_get_floating_widgets_test)

        check_widget_docked_action = test_menu.addAction("Test: Is Widget Docked?")
        check_widget_docked_action.triggered.connect(self.run_is_widget_docked_test)

        programmatic_dock_action = test_menu.addAction("Test: Programmatic Dock")
        programmatic_dock_action.triggered.connect(self.run_programmatic_dock_test)

        programmatic_undock_action = test_menu.addAction("Test: Programmatic Undock")
        programmatic_undock_action.triggered.connect(self.run_programmatic_undock_test)

        programmatic_move_action = test_menu.addAction("Test: Programmatic Move to Main")
        programmatic_move_action.triggered.connect(self.run_programmatic_move_test)

        activate_widget_action = test_menu.addAction("Test: Activate Widget")
        activate_widget_action.triggered.connect(self.run_activate_widget_test)

        test_menu.addSeparator()

        self.debug_mode_action = test_menu.addAction("Toggle Debug Mode")
        self.debug_mode_action.setCheckable(True)
        self.debug_mode_action.setChecked(self.docking_manager.debug_mode)
        self.debug_mode_action.triggered.connect(self.docking_manager.set_debug_mode)


    def _create_test_content(self, name: str) -> QWidget:
        """Creates a simple ttest_widget_3able with test data for demonstration."""
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)

        table_widget = QTableWidget()

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

        for row in range(5):
            item_id = QTableWidgetItem(f"{name}-I{row+1}")
            item_desc = QTableWidgetItem(f"Sample data item for row {row+1}")
            item_value = QTableWidgetItem(str(random.randint(100, 999)))

            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_value.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            table_widget.setItem(row, 0, item_id)
            table_widget.setItem(row, 1, item_desc)
            table_widget.setItem(row, 2, item_value)

        table_widget.resizeColumnsToContents()

        content_layout.addWidget(table_widget)

        return content_widget

    def create_and_register_new_widget(self):
        """This application-level function creates a widget and registers it with the manager."""
        self.widget_count += 1
        widget_name = f"Widget {self.widget_count}"
        persistent_id = f"test_widget_{self.widget_count}"

        new_dockable_widget = self._create_and_configure_widget(widget_name, persistent_id)

        # Add widget to manager's widget list (but don't register as floating)
        new_dockable_widget.manager = self.docking_manager
        self.docking_manager.widgets.append(new_dockable_widget)
        self.docking_manager.add_widget_handlers(new_dockable_widget)
        
        # Create a floating window using DockContainer
        geometry = QRect(200 + self.widget_count * 40, 200 + self.widget_count * 40, 400, 300)
        self.docking_manager.create_floating_window([new_dockable_widget], geometry)

    def _create_and_configure_widget(self, name: str, persistent_id: str) -> DockPanel:
        """Helper method that creates and a single dockable widget."""
        new_dockable_widget = DockPanel(
            name,
            parent=None,
            manager=self.docking_manager,
            persistent_id=persistent_id
        )

        test_content = self._create_test_content(name)
        new_dockable_widget.setContent(test_content)

        return new_dockable_widget

    def app_widget_factory(self, node_data: dict) -> DockPanel:
        """
        This is the application's factory. The docking manager will call this
        during a 'load' operation to recreate a widget from its saved ID.
        """
        persistent_id = node_data.get('id')
        margin_size = node_data.get('margin', 5)

        print(f"Factory called to create widget with ID: {persistent_id}")
        match = re.search(r'\d+$', persistent_id)
        widget_num = match.group(0) if match else "N/A"
        widget_name = f"Widget {widget_num}"

        new_dockable_widget = DockPanel(
            widget_name,
            parent=None,
            manager=self.docking_manager,
            persistent_id=persistent_id
        )

        test_content = self._create_test_content(widget_name)
        new_dockable_widget.setContent(test_content, margin_size=margin_size)

        return new_dockable_widget

    def save_layout(self):
        """Saves the current docking layout to an internal variable."""
        print("\n--- RUNNING TEST: Save Layout ---")
        try:
            self.saved_layout_data = self.docking_manager.save_layout_to_bytearray()
            print("SUCCESS: Layout saved to memory.")
        except Exception as e:
            print(f"FAILURE: Could not save layout: {e}")
        print("---------------------------------")

    def load_layout(self):
        """Loads the previously saved docking layout."""
        print("\n--- RUNNING TEST: Load Layout ---")
        if self.saved_layout_data:
            try:
                self.docking_manager.load_layout_from_bytearray(self.saved_layout_data)
                print("SUCCESS: Layout loaded from memory.")
            except Exception as e:
                print(f"FAILURE: Could not load layout: {e}")
        else:
            print("INFO: No layout data saved yet. Please save a layout first.")
        print("---------------------------------")


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
            found_widget.set_title_bar_color(QColor("#DDA0DD"))
            found_widget.on_activation_request()
        else:
            print(f"FAILURE: Could not find widget with ID: '{target_id}'")
        print("-------------------------------------------------")


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
                widget.set_title_bar_color(QColor("#90EE90"))

        print("--------------------------------------------")

    def run_is_widget_docked_test(self):
        """
        Tests the manager's is_widget_docked method.
        """
        target_id = "test_widget_1"
        print(f"\n--- RUNNING TEST: Check if '{target_id}' is docked ---")
        widget_to_check = self.docking_manager.find_widget_by_id(target_id)

        if not widget_to_check:
            print(f"FAILURE: Cannot find '{target_id}' to perform test. Please create Widget 1.")
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
            print(f"FAILURE: Cannot find source widget '{source_id}'. Please create Widget 1.")
            return
        if not target_widget:
            print(f"FAILURE: Cannot find target widget '{target_id}'. Please create Widget 2.")
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
            print(f"FAILURE: Cannot find source widget '{source_id}'. Please create Widget 3.")
            return

        if not self.docking_manager.is_widget_docked(source_widget):
            print("INFO: Docking widget into main window first to prepare for test...")
            self.docking_manager.dock_widget(source_widget, target_container, "center")
            self.app.processEvents()

        print(f"SUCCESS: Found and ensured widget is docked. Attempting to undock...")
        self.docking_manager.undock_widget(source_widget)
        print("-------------------------------------------------------------------")

    def run_programmatic_move_test(self):
        """
        Tests programmatically moving a widget to a different container (the main window's dock area).
        """
        source_id = "test_widget_1"
        target_container = self.main_window.dock_area
        print(f"\n--- RUNNING TEST: Programmatically move '{source_id}' to the main window ---")

        source_widget = self.docking_manager.find_widget_by_id(source_id)
        if not source_widget:
            print(f"FAILURE: Cannot find source widget '{source_id}'. Please create Widget 1.")
            return

        if self.docking_manager.is_widget_docked(source_widget):
            self.docking_manager.undock_widget(source_widget)
            self.app.processEvents()

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
        self.app.processEvents()

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
        print("\n=== APPLICATION READY FOR MANUAL TESTING ===")
        print("You can now manually drag widgets to test docking behavior.")
        print("Debug output will appear in this console.")
        print("Close the application window to exit.")
        print("=" * 50 + "\n")
        return self.app.exec()

if __name__ == "__main__":
    test_app = DockingTestApp()
    test_app.run()
