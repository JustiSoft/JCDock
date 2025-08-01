"""
Test utility functions for the JCDock test suite.
Common helper functions for test execution and validation.
"""

from typing import List, Optional
from PySide6.QtGui import QColor
from PySide6.QtCore import QObject
from JCDock.widgets.dock_panel import DockPanel


class TestUtilities:
    """Common utility functions for test operations."""
    
    @staticmethod
    def print_test_header(test_name: str):
        """Print a consistent test header."""
        print(f"\n--- RUNNING TEST: {test_name} ---")
    
    @staticmethod
    def print_test_footer():
        """Print a consistent test footer."""
        print("-" * 50)
    
    @staticmethod
    def print_success(message: str):
        """Print a success message."""
        print(f"SUCCESS: {message}")
    
    @staticmethod
    def print_failure(message: str):
        """Print a failure message."""
        print(f"FAILURE: {message}")
    
    @staticmethod
    def print_info(message: str):
        """Print an info message."""
        print(f"INFO: {message}")
    
    @staticmethod
    def reset_widget_visual_state(widget: DockPanel):
        """Reset any visual modifications made to a widget during testing."""
        if not widget:
            return
            
        # Remove any test markers from title
        original_title = widget.windowTitle()
        test_markers = [" (Found!)", "(Listed) ", " (MANUAL)", " (RESTORED ✓)"]
        
        for marker in test_markers:
            if marker in original_title:
                original_title = original_title.replace(marker, "")
        
        widget.set_title(original_title)
        
        # Reset title bar color to default
        widget.set_title_bar_color(None)
    
    @staticmethod
    def validate_widget_exists(docking_manager, persistent_id: str) -> bool:
        """Validate that a widget with the given ID exists in the manager."""
        return docking_manager.find_widget_by_id(persistent_id) is not None
    
    @staticmethod
    def is_widget_truly_docked(widget: DockPanel, docking_manager) -> bool:
        """
        Determine if a widget is truly docked (in a container with multiple widgets).
        Single widget containers are considered floating, not docked.
        """
        if not widget or not widget.parent_container:
            return False
        
        # Find the container holding this widget
        for root_window in docking_manager.model.roots.keys():
            if hasattr(root_window, 'contained_widgets'):
                contained = getattr(root_window, 'contained_widgets', [])
                if widget in contained:
                    # Widget is truly docked only if container has multiple widgets
                    return len(contained) > 1
        return False
    
    @staticmethod
    def validate_widget_state(widget: DockPanel, expected_docked: bool, docking_manager) -> bool:
        """Validate that a widget is in the expected docked/floating state."""
        if not widget:
            return False
        actual_docked = TestUtilities.is_widget_truly_docked(widget, docking_manager)
        return actual_docked == expected_docked
    
    @staticmethod
    def cleanup_test_modifications(docking_manager):
        """Clean up any visual modifications made during testing."""
        all_widgets = docking_manager.get_all_widgets()
        for widget in all_widgets:
            TestUtilities.reset_widget_visual_state(widget)
    
    @staticmethod
    def run_test_with_isolation(test_name: str, test_func, docking_manager, app):
        """Run a test function with proper setup and teardown."""
        TestUtilities.print_test_header(test_name)
        TestUtilities.cleanup_test_modifications(docking_manager)
        
        try:
            test_func()
        except Exception as e:
            TestUtilities.print_failure(f"Test failed with exception: {e}")
        finally:
            TestUtilities.cleanup_test_modifications(docking_manager)
            app.processEvents()
            TestUtilities.print_test_footer()


class EventListener(QObject):
    """
    A simple event listener to demonstrate connecting to DockingManager signals.
    """
    
    def on_widget_docked(self, widget, container):
        """Handle widget docked signal."""
        container_name = container.windowTitle()
        if container.objectName() == "MainDockArea":
            container_name = "Main Dock Area"
    
    def on_widget_undocked(self, widget):
        """Handle widget undocked signal."""
        pass
    
    def on_widget_closed(self, persistent_id):
        """Handle widget closed signal."""
        pass
    
    def on_layout_changed(self):
        """Handle layout changed signal."""
        pass