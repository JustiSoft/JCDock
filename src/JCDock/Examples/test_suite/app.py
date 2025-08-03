"""
Main application class for the JCDock test suite.
Refactored from the original monolithic dock_test.py for better maintainability.
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QMenuBar
from PySide6.QtCore import QSize

from JCDock.core.docking_manager import DockingManager
from JCDock.widgets.dock_container import DockContainer
from JCDock.core.widget_registry import get_registry

from .managers.test_manager import TestManager
from .managers.layout_manager import LayoutManager
from .managers.ui_manager import UIManager
from .utils.test_utilities import EventListener
from .utils.constants import MAIN_WINDOW_POSITION, LARGE_WINDOW_SIZE, APPLICATION_NAME


class DockingTestApp:
    """
    Main application class for testing the JCDock library.
    Refactored to use focused manager classes for different responsibilities.
    """
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName(APPLICATION_NAME)

        # Initialize core docking system
        self.docking_manager = DockingManager()
        
        # Create main window
        self._create_main_window()
        
        # Initialize manager classes
        self.layout_manager = LayoutManager(self.docking_manager, self.main_window)
        self.test_manager = TestManager(self.docking_manager, self.main_window, self.app)
        self.ui_manager = UIManager(self)
        
        # Setup event handling
        self._setup_event_handling()
        
        # Register widget factories and state handlers
        self._register_custom_widgets()
        
        # Create the UI
        self._create_ui()
    
    def _create_main_window(self):
        """Create and configure the main application window."""
        self.main_window = self.docking_manager.create_window(
            is_main_window=True,
            title=APPLICATION_NAME,
            x=MAIN_WINDOW_POSITION.x(),
            y=MAIN_WINDOW_POSITION.y(),
            width=LARGE_WINDOW_SIZE.width(),
            height=LARGE_WINDOW_SIZE.height(),
            auto_persistent_root=True,
            preserve_title=True
        )
        self.main_window.setObjectName("MainDockArea")
        
        # Add menu bar support
        self.main_window._menu_bar = QMenuBar(self.main_window)
        
        # Update layout to include menu bar
        if self.main_window.layout():
            self.main_window.layout().insertWidget(1, self.main_window._menu_bar)
    
    def _setup_event_handling(self):
        """Setup signal connections for docking events."""
        self.event_listener = EventListener()
        signals = self.docking_manager.signals
        
        signals.widget_docked.connect(self.event_listener.on_widget_docked)
        signals.widget_undocked.connect(self.event_listener.on_widget_undocked)
        signals.widget_closed.connect(self.event_listener.on_widget_closed)
        signals.layout_changed.connect(self.event_listener.on_layout_changed)
    
    def _register_custom_widgets(self):
        """Register custom widget factories and state handlers."""
        registry = get_registry()
        
        # Register ad-hoc stateful widget if not already registered
        if not registry.is_registered("adhoc_stateful_widget"):
            self.docking_manager.register_widget_factory(
                key="adhoc_stateful_widget",
                factory=self.ui_manager._create_adhoc_stateful_widget,
                title="Ad-Hoc Stateful Widget"
            )
            
            # Register state handlers for this widget type
            self.docking_manager.register_instance_state_handlers(
                persistent_key="adhoc_stateful_widget",
                state_provider=self.ui_manager._extract_adhoc_widget_state,
                state_restorer=self.ui_manager._restore_adhoc_widget_state
            )
    
    def _create_ui(self):
        """Create the user interface elements."""
        self.ui_manager.create_test_menu_bar()
    
    def run(self):
        """Start the application with optional layout loading."""
        self.main_window.show()
        
        # Try to load saved layout first
        print("Checking for saved layout...")
        layout_loaded = self.layout_manager.load_layout_silently()
        
        if layout_loaded:
            layout_path = self.layout_manager.get_standard_layout_path()
            print(f"SUCCESS: Loaded saved layout from {layout_path}")
            widget_count = len(self.docking_manager.widgets)
            print(f"Startup complete! Restored {widget_count} widgets from saved layout.")
        else:
            print("No saved layout found. Starting with empty layout.")
            print("Startup complete! Use the 'Widgets' menu to create widgets.")
        
        self._print_startup_info()
        
        return self.app.exec()
    
    def _print_startup_info(self):
        """Print helpful startup information."""
        print("Use the 'Colors' menu to test color customization features.")
        print("Use the 'Icons' menu to test icon functionality.")
        print("Use the 'File' menu to save/load layouts.")
        print("Use the 'Tests' menu to run comprehensive test suites.")