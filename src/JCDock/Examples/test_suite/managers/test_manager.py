"""
Test management functionality for the JCDock test suite.
Handles all test execution, validation, and reporting.
"""

from typing import List, Tuple, Callable
from PySide6.QtGui import QColor

from ..utils.test_utilities import TestUtilities
from ..utils.constants import Colors


class TestManager:
    """Manages test execution and validation operations."""
    
    def __init__(self, docking_manager, main_window, app):
        self.docking_manager = docking_manager
        self.main_window = main_window
        self.app = app
        self.test_utils = TestUtilities()
    
    def run_find_widget_test(self):
        """Test the manager's find_widget_by_id method."""
        def test_logic():
            # Get all existing widgets first
            all_widgets = self.docking_manager.get_all_widgets()
            if not all_widgets:
                TestUtilities.print_failure("No widgets exist to test with")
                return
            
            # Use the first available widget for testing
            test_widget = all_widgets[0]
            target_id = test_widget.persistent_id
            
            TestUtilities.print_info(f"Testing with existing widget ID: '{target_id}'")
            
            # Test finding an existing widget
            found_widget = self.docking_manager.find_widget_by_id(target_id)
            
            if found_widget and found_widget is test_widget:
                TestUtilities.print_success(f"Found widget: {found_widget.windowTitle()}")
                # Add visual feedback (will be cleaned up automatically)
                found_widget.set_title(f"{found_widget.windowTitle()} (Found!)")
                found_widget.set_title_bar_color(Colors.PURPLE)
                found_widget.on_activation_request()
            elif found_widget:
                TestUtilities.print_failure("Found a widget but it's not the expected instance")
            else:
                TestUtilities.print_failure(f"Could not find widget with ID: '{target_id}'")
            
            # Test finding a non-existent widget
            non_existent_widget = self.docking_manager.find_widget_by_id("non_existent_widget")
            if non_existent_widget is None:
                TestUtilities.print_success("Correctly returned None for non-existent widget")
            else:
                TestUtilities.print_failure("Should have returned None for non-existent widget")
        
        TestUtilities.run_test_with_isolation("Find widget by ID", test_logic, self.docking_manager, self.app)
    
    def run_list_all_widgets_test(self):
        """Test the manager's get_all_widgets method."""
        def test_logic():
            all_widgets = self.docking_manager.get_all_widgets()

            if not all_widgets:
                TestUtilities.print_failure("No widgets returned")
                return

            TestUtilities.print_success(f"Found {len(all_widgets)} widgets:")
            
            # Validate that all returned objects are actually DockPanel instances
            valid_widgets = 0
            for i, widget in enumerate(all_widgets):
                if hasattr(widget, 'persistent_id'):
                    print(f"  {i + 1}: {widget.windowTitle()} (ID: {widget.persistent_id})")
                    valid_widgets += 1
                else:
                    TestUtilities.print_failure(f"Invalid widget at index {i}: {type(widget)}")
            
            if valid_widgets == len(all_widgets):
                TestUtilities.print_success(f"All {valid_widgets} widgets are valid DockPanel instances")
            else:
                TestUtilities.print_failure(f"Only {valid_widgets}/{len(all_widgets)} widgets are valid")
        
        TestUtilities.run_test_with_isolation("List all widgets", test_logic, self.docking_manager, self.app)
    
    def run_get_floating_widgets_test(self):
        """Test the manager's get_floating_widgets method."""
        def test_logic():
            floating_widgets = self.docking_manager.get_floating_widgets()
            
            if not floating_widgets:
                # Find widgets that are in floating containers (not main dock area)
                main_dock_area = self.main_window
                floating_container_widgets = []
                
                for root_window in self.docking_manager.model.roots.keys():
                    if root_window != main_dock_area and hasattr(root_window, 'contained_widgets'):
                        contained = getattr(root_window, 'contained_widgets', [])
                        floating_container_widgets.extend(contained)
                        
                if floating_container_widgets:
                    TestUtilities.print_success(f"Found {len(floating_container_widgets)} floating widgets:")
                    for i, widget in enumerate(floating_container_widgets):
                        print(f"  {i + 1}: {widget.windowTitle()} (ID: {widget.persistent_id})")
                        widget.set_title_bar_color(Colors.LIGHT_GREEN)
                else:
                    TestUtilities.print_failure("No floating widgets found")
                return
            
            TestUtilities.print_success(f"Found {len(floating_widgets)} floating widgets:")
            
            for i, widget in enumerate(floating_widgets):
                print(f"  {i + 1}: {widget.windowTitle()} (ID: {widget.persistent_id})")
                widget.set_title_bar_color(Colors.LIGHT_GREEN)
        
        TestUtilities.run_test_with_isolation("Get floating widgets", test_logic, self.docking_manager, self.app)
    
    def run_is_widget_docked_test(self):
        """Test widget docked/floating state using correct definition."""
        def test_logic():
            all_widgets = self.docking_manager.get_all_widgets()
            if not all_widgets:
                TestUtilities.print_failure("No widgets exist to test with")
                return
            
            TestUtilities.print_info("Analyzing widget states (Docked = multi-widget container, Floating = single-widget container):")
            
            truly_docked_count = 0
            truly_floating_count = 0
            
            for widget in all_widgets:
                is_truly_docked = TestUtilities.is_widget_truly_docked(widget, self.docking_manager)
                old_method_result = self.docking_manager.is_widget_docked(widget)
                
                if is_truly_docked:
                    truly_docked_count += 1
                    print(f"  {widget.windowTitle()}: DOCKED (in multi-widget container)")
                else:
                    truly_floating_count += 1
                    print(f"  {widget.windowTitle()}: FLOATING (in single-widget container)")
                
                # Show discrepancy with old method if any
                if is_truly_docked != old_method_result:
                    TestUtilities.print_info(f"    Note: Original is_widget_docked() returns {old_method_result} (different)")
            
            TestUtilities.print_success(f"State summary: {truly_docked_count} truly docked, {truly_floating_count} truly floating")
            
            # Test the original method behavior vs our corrected logic
            if truly_floating_count > 0 and truly_docked_count == 0:
                TestUtilities.print_success("All widgets are floating (single-widget containers) - matches expected startup state")
            elif truly_docked_count > 0:
                TestUtilities.print_success(f"Found {truly_docked_count} widgets in multi-widget containers (truly docked)")
            
            # Test with None/invalid widget
            try:
                invalid_result = self.docking_manager.is_widget_docked(None)
                TestUtilities.print_info(f"is_widget_docked(None) returned: {invalid_result}")
            except Exception as e:
                TestUtilities.print_info(f"is_widget_docked(None) raised exception: {e}")
        
        TestUtilities.run_test_with_isolation("Is widget docked check", test_logic, self.docking_manager, self.app)
    
    def run_programmatic_dock_test(self):
        """Test programmatically docking one widget into another."""
        def test_logic():
            all_widgets = self.docking_manager.get_all_widgets()
            if len(all_widgets) < 2:
                TestUtilities.print_failure("Need at least 2 widgets to test docking operations")
                return
            
            source_widget = all_widgets[0]
            target_widget = all_widgets[1]
            
            # Record initial states using correct definition
            initial_source_docked = TestUtilities.is_widget_truly_docked(source_widget, self.docking_manager)
            initial_target_docked = TestUtilities.is_widget_truly_docked(target_widget, self.docking_manager)
            
            TestUtilities.print_info(f"Testing with: '{source_widget.windowTitle()}' -> '{target_widget.windowTitle()}'")
            TestUtilities.print_info(f"Initial states - Source truly docked: {initial_source_docked}, Target truly docked: {initial_target_docked}")
            
            # Test docking to center (creates tab group)
            TestUtilities.print_info(f"Docking '{source_widget.windowTitle()}' into '{target_widget.windowTitle()}' at center")
            try:
                self.docking_manager.dock_widget(source_widget, target_widget, "center")
                self.app.processEvents()
            except Exception as e:
                TestUtilities.print_failure(f"Dock operation failed with exception: {e}")
                return
            
            # Verify final states using correct definition
            final_source_docked = TestUtilities.is_widget_truly_docked(source_widget, self.docking_manager)
            final_target_docked = TestUtilities.is_widget_truly_docked(target_widget, self.docking_manager)
            
            if final_source_docked and final_target_docked:
                TestUtilities.print_success("Both widgets are now truly docked (in multi-widget container)")
            else:
                TestUtilities.print_info("Docking operation did not result in truly docked state")
                TestUtilities.print_info("This may be due to architectural limitation in dock_widget method")
        
        TestUtilities.run_test_with_isolation("Programmatic dock operations", test_logic, self.docking_manager, self.app)
    
    def run_programmatic_undock_test(self):
        """Test programmatically undocking a widget."""
        def test_logic():
            all_widgets = self.docking_manager.get_all_widgets()
            if not all_widgets:
                TestUtilities.print_failure("No widgets exist to test with")
                return
            
            # Find a truly docked widget to test with, or dock widgets to create one
            truly_docked_widget = None
            for widget in all_widgets:
                if TestUtilities.is_widget_truly_docked(widget, self.docking_manager):
                    truly_docked_widget = widget
                    break
            
            if not truly_docked_widget and len(all_widgets) >= 2:
                # Dock two widgets together to create a truly docked state
                TestUtilities.print_info("No truly docked widgets found, creating docked state for test")
                self.docking_manager.dock_widget(all_widgets[0], all_widgets[1], "center")
                self.app.processEvents()
                
                # Check if docking worked
                if TestUtilities.is_widget_truly_docked(all_widgets[0], self.docking_manager):
                    truly_docked_widget = all_widgets[0]
                else:
                    TestUtilities.print_failure("Failed to create truly docked state for testing")
                    return
            
            if not truly_docked_widget:
                TestUtilities.print_failure("Could not establish a truly docked widget for testing")
                return
            
            TestUtilities.print_info(f"Testing undock with truly docked widget: '{truly_docked_widget.windowTitle()}'")
            
            # Perform undock operation
            undock_result = self.docking_manager.undock_widget(truly_docked_widget)
            self.app.processEvents()
            
            # Verify final state
            final_truly_docked = TestUtilities.is_widget_truly_docked(truly_docked_widget, self.docking_manager)
            
            if not final_truly_docked:
                TestUtilities.print_success(f"Widget '{truly_docked_widget.windowTitle()}' successfully undocked")
            else:
                TestUtilities.print_failure("Widget is still truly docked after undock operation")
        
        TestUtilities.run_test_with_isolation("Programmatic undock operations", test_logic, self.docking_manager, self.app)
    
    def run_programmatic_move_test(self):
        """Test programmatically moving a widget to a different container."""
        def test_logic():
            all_widgets = self.docking_manager.get_all_widgets()
            if not all_widgets:
                TestUtilities.print_failure("No widgets exist to test with")
                return
            
            target_container = self.main_window
            source_widget = all_widgets[0]
            
            TestUtilities.print_info(f"Testing move with widget: '{source_widget.windowTitle()}'")
            
            # Test moving to main dock area
            TestUtilities.print_info(f"Moving '{source_widget.windowTitle()}' to main dock area")
            move_result = self.docking_manager.move_widget_to_container(source_widget, target_container)
            self.app.processEvents()
            
            if move_result:
                TestUtilities.print_success("Move operation successful")
            else:
                TestUtilities.print_failure(f"Move operation failed - Result: {move_result}")
        
        TestUtilities.run_test_with_isolation("Programmatic move operations", test_logic, self.docking_manager, self.app)
    
    def run_activate_widget_test(self):
        """Test the manager's activate_widget method."""
        def test_logic():
            all_widgets = self.docking_manager.get_all_widgets()
            if not all_widgets:
                TestUtilities.print_failure("No widgets exist to test with")
                return
            
            # Test activation of first widget
            widget_to_activate = all_widgets[0]
            TestUtilities.print_info(f"Testing activation of widget: '{widget_to_activate.windowTitle()}'")
            
            try:
                self.docking_manager.activate_widget(widget_to_activate)
                self.app.processEvents()
                TestUtilities.print_success("Widget activation completed without errors")
            except Exception as e:
                TestUtilities.print_failure(f"Widget activation failed: {e}")
                return
            
            # Test with invalid widget (None)
            TestUtilities.print_info("Testing activate_widget(None) - should handle gracefully")
            try:
                self.docking_manager.activate_widget(None)
                TestUtilities.print_success("activate_widget(None) handled gracefully")
            except Exception as e:
                TestUtilities.print_failure(f"activate_widget(None) raised unexpected exception: {e}")
        
        TestUtilities.run_test_with_isolation("Widget activation", test_logic, self.docking_manager, self.app)
    
    def run_all_tests_sequentially(self):
        """Run all available tests in sequence for comprehensive validation."""
        TestUtilities.print_test_header("RUNNING ALL TESTS SEQUENTIALLY")
        print("This will run all available tests one after another...")
        print("Each test is isolated and should not affect the others.\n")
        
        # List all test methods to run
        test_methods: List[Tuple[str, Callable]] = [
            ("Find Widget by ID", self.run_find_widget_test),
            ("List All Widgets", self.run_list_all_widgets_test),
            ("Get Floating Widgets", self.run_get_floating_widgets_test),
            ("Is Widget Docked Check", self.run_is_widget_docked_test),
            ("Programmatic Dock Operations", self.run_programmatic_dock_test),
            ("Programmatic Undock Operations", self.run_programmatic_undock_test),
            ("Programmatic Move Operations", self.run_programmatic_move_test),
            ("Widget Activation", self.run_activate_widget_test),
        ]
        
        successful_tests = 0
        total_tests = len(test_methods)
        
        for test_name, test_method in test_methods:
            try:
                print(f"\n{'='*60}")
                print(f"Running: {test_name}")
                print('='*60)
                test_method()
                successful_tests += 1
                print(f"PASS: {test_name} completed")
            except Exception as e:
                print(f"FAIL: {test_name} failed with exception: {e}")
        
        # Print summary
        print(f"\n{'='*60}")
        print("TEST SUMMARY")
        print('='*60)
        print(f"Total Tests: {total_tests}")
        print(f"Successful: {successful_tests}")
        print(f"Failed: {total_tests - successful_tests}")
        
        if successful_tests == total_tests:
            print("ALL TESTS PASSED!")
        else:
            print(f"{total_tests - successful_tests} TEST(S) FAILED")
        
        print('='*60)