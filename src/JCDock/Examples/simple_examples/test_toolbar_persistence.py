"""
Test script for toolbar persistence functionality.
Creates toolbars, saves layout, clears, then restores to verify persistence works.
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QToolBar
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from JCDock.core.docking_manager import DockingManager


def test_toolbar_persistence():
    """Test toolbar state persistence through save/load cycle."""
    print("Testing toolbar persistence...")
    
    app = QApplication(sys.argv)
    manager = DockingManager()
    
    # Create main window
    main_window = manager.create_window(
        is_main_window=True,
        title="Toolbar Persistence Test",
        x=100, y=100, width=800, height=600,
        auto_persistent_root=True
    )
    
    print("Phase 1: Creating initial toolbar configuration...")
    
    # Create complex toolbar configuration
    file_toolbar = main_window.addToolBar("File Operations")
    file_toolbar.setObjectName("FileToolbar")
    
    edit_toolbar = main_window.addToolBar("Edit Operations")
    edit_toolbar.setObjectName("EditToolbar")
    
    # Add break - next toolbar should be in new row
    main_window.addToolBarBreak(Qt.TopToolBarArea)
    
    view_toolbar = main_window.addToolBar("View Options")
    view_toolbar.setObjectName("ViewToolbar")
    
    # Bottom area
    status_toolbar = main_window.addToolBar("Status", Qt.BottomToolBarArea)
    status_toolbar.setObjectName("StatusToolbar")
    
    # Left area with multiple columns
    tools_toolbar = main_window.addToolBar("Tools", Qt.LeftToolBarArea)
    tools_toolbar.setObjectName("ToolsToolbar")
    
    main_window.addToolBarBreak(Qt.LeftToolBarArea)
    
    palette_toolbar = main_window.addToolBar("Palette", Qt.LeftToolBarArea)
    palette_toolbar.setObjectName("PaletteToolbar")
    
    # Add some actions
    file_action = QAction("New", main_window)
    file_toolbar.addAction(file_action)
    
    edit_action = QAction("Copy", main_window)
    edit_toolbar.addAction(edit_action)
    
    print(f"Created {len(main_window.toolBars())} toolbars")
    print("Toolbar areas:", [(tb.windowTitle(), main_window.toolBarArea(tb)) for tb in main_window.toolBars()])
    print("Toolbar breaks:", [(tb.windowTitle(), main_window.toolBarBreak(tb)) for tb in main_window.toolBars()])
    
    print("\nPhase 2: Saving layout...")
    
    # Save layout
    try:
        layout_data = manager.save_layout_to_bytearray()
        with open("test_toolbar_layout.bin", "wb") as f:
            f.write(layout_data)
        print("Layout saved successfully")
    except Exception as e:
        print(f"Save failed: {e}")
        return False
    
    print("\nPhase 3: Clearing current toolbars...")
    
    # Clear all toolbars
    toolbars_to_remove = main_window.toolBars().copy()
    for toolbar in toolbars_to_remove:
        main_window.removeToolBar(toolbar)
    
    print(f"Cleared toolbars, remaining: {len(main_window.toolBars())}")
    
    print("\nPhase 4: Loading layout...")
    
    # Load layout
    try:
        with open("test_toolbar_layout.bin", "rb") as f:
            layout_data = f.read()
        manager.load_layout_from_bytearray(layout_data)
        print("Layout loaded successfully")
    except Exception as e:
        print(f"Load failed: {e}")
        return False
    
    print("\nPhase 5: Verifying restored state...")
    
    restored_toolbars = main_window.toolBars()
    print(f"Restored {len(restored_toolbars)} toolbars")
    
    # Verify toolbar configuration
    expected_titles = ["File Operations", "Edit Operations", "View Options", "Status", "Tools", "Palette"]
    restored_titles = [tb.windowTitle() for tb in restored_toolbars]
    
    print("Expected titles:", expected_titles)
    print("Restored titles:", restored_titles)
    
    # Check if all expected toolbars are present
    missing = set(expected_titles) - set(restored_titles)
    extra = set(restored_titles) - set(expected_titles)
    
    if missing:
        print(f"ERROR: Missing toolbars: {missing}")
        return False
    
    if extra:
        print(f"WARNING: Extra toolbars: {extra}")
    
    # Verify areas
    print("Restored toolbar areas:", [(tb.windowTitle(), main_window.toolBarArea(tb)) for tb in restored_toolbars])
    print("Restored toolbar breaks:", [(tb.windowTitle(), main_window.toolBarBreak(tb)) for tb in restored_toolbars])
    
    # Verify specific toolbar areas
    area_checks = [
        ("File Operations", Qt.TopToolBarArea),
        ("Edit Operations", Qt.TopToolBarArea), 
        ("View Options", Qt.TopToolBarArea),
        ("Status", Qt.BottomToolBarArea),
        ("Tools", Qt.LeftToolBarArea),
        ("Palette", Qt.LeftToolBarArea)
    ]
    
    for title, expected_area in area_checks:
        toolbar = next((tb for tb in restored_toolbars if tb.windowTitle() == title), None)
        if toolbar:
            actual_area = main_window.toolBarArea(toolbar)
            if actual_area != expected_area:
                print(f"ERROR: {title} should be in {expected_area}, but is in {actual_area}")
                return False
        else:
            print(f"ERROR: Toolbar '{title}' not found")
            return False
    
    # Verify breaks - Edit Operations should have a break after it
    edit_toolbar = next((tb for tb in restored_toolbars if tb.windowTitle() == "Edit Operations"), None)
    if edit_toolbar:
        has_break = main_window.toolBarBreak(edit_toolbar)
        if not has_break:
            print("ERROR: Edit Operations toolbar should have a break after it")
            return False
    
    # Verify Tools toolbar has break
    tools_toolbar = next((tb for tb in restored_toolbars if tb.windowTitle() == "Tools"), None)
    if tools_toolbar:
        has_break = main_window.toolBarBreak(tools_toolbar)
        if not has_break:
            print("ERROR: Tools toolbar should have a break after it")
            return False
    
    print("\nAll tests passed! Toolbar persistence is working correctly.")
    
    # Clean up
    try:
        os.remove("test_toolbar_layout.bin")
        print("Test file cleaned up")
    except:
        pass
    
    return True


if __name__ == "__main__":
    success = test_toolbar_persistence()
    sys.exit(0 if success else 1)