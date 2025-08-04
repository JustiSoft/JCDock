"""
Enhanced Toolbar Demo - JCDock Simple Example

This script demonstrates the enhanced toolbar functionality:
- Multiple toolbar areas (top, bottom, left, right)
- Toolbar breaks for multiple rows/columns
- Toolbar insertion and positioning
- Toolbar persistence through save/load
- Complete QMainWindow-like toolbar API

Shows all new toolbar methods: addToolBarBreak, insertToolBar, insertToolBarBreak,
toolBarArea, toolBarBreak, and full toolbar state persistence.
"""

import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QMenuBar, QStatusBar, QToolBar
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Qt
from JCDock.core.docking_manager import DockingManager
from JCDock.widgets.dock_container import DockContainer


def create_content_widget(widget_num: int) -> QWidget:
    """Create a simple content widget for demonstration."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    
    # Title
    title = QLabel(f"Enhanced Toolbar Demo Widget {widget_num}")
    title.setStyleSheet("font-weight: bold; font-size: 16px; color: #2c3e50; padding: 10px;")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)
    
    # Content
    content = QLabel(f"This demonstrates enhanced toolbar functionality.\nTry the toolbar management features and save/load.")
    content.setStyleSheet("color: #666; padding: 10px;")
    content.setAlignment(Qt.AlignmentFlag.AlignCenter)
    content.setWordWrap(True)
    layout.addWidget(content)
    
    # Button
    button = QPushButton(f"Test Action {widget_num}")
    button.clicked.connect(lambda: print(f"Test Action {widget_num} executed!"))
    layout.addWidget(button)
    
    return widget


def main():
    # Create the Qt application
    app = QApplication(sys.argv)
    
    # Create the docking manager
    manager = DockingManager()
    
    # Create main window using unified API
    main_window = manager.create_window(
        is_main_window=True,
        title="JCDock Enhanced Toolbar Demo",
        x=200, y=200, width=900, height=700,
        auto_persistent_root=True
    )
    main_window.setObjectName("MainWindow")
    
    # Add menu bar
    menu_bar = QMenuBar(main_window)
    main_window.layout().insertWidget(1, menu_bar)
    main_window._menu_bar = menu_bar
    
    # Add status bar
    status_bar = QStatusBar(main_window)
    main_window.layout().addWidget(status_bar)
    main_window._status_bar = status_bar
    status_bar.showMessage("Ready - Enhanced toolbar demo with breaks, insertion, and persistence")
    
    # Create multiple toolbars with breaks to demonstrate advanced functionality
    
    # === TOP AREA - Multiple rows with breaks ===
    file_toolbar = main_window.addToolBar("File Operations")
    file_toolbar.setObjectName("FileToolbar")
    edit_toolbar = main_window.addToolBar("Edit Operations")  # Same row
    edit_toolbar.setObjectName("EditToolbar")
    
    # Add a toolbar break to create a new row
    main_window.addToolBarBreak(Qt.TopToolBarArea)
    
    view_toolbar = main_window.addToolBar("View Options")  # New row
    view_toolbar.setObjectName("ViewToolbar")
    debug_toolbar = main_window.addToolBar("Debug Tools")  # Same row as view
    debug_toolbar.setObjectName("DebugToolbar")
    
    # === BOTTOM AREA - Demonstrate insertToolBar ===
    status_toolbar = main_window.addToolBar("Status Info", Qt.BottomToolBarArea)
    status_toolbar.setObjectName("StatusToolbar")
    
    # Insert a toolbar before the status toolbar
    info_toolbar = main_window.insertToolBar(status_toolbar, "System Info")
    info_toolbar.setObjectName("InfoToolbar")
    
    # === LEFT AREA - Multiple columns ===
    tools_toolbar = main_window.addToolBar("Tools", Qt.LeftToolBarArea)
    tools_toolbar.setObjectName("ToolsToolbar")
    
    # Add break for new column
    main_window.addToolBarBreak(Qt.LeftToolBarArea)
    
    palette_toolbar = main_window.addToolBar("Palette", Qt.LeftToolBarArea)
    palette_toolbar.setObjectName("PaletteToolbar")
    
    # === RIGHT AREA - Test insertToolBarBreak ===
    format_toolbar = main_window.addToolBar("Format", Qt.RightToolBarArea)
    format_toolbar.setObjectName("FormatToolbar")
    props_toolbar = main_window.addToolBar("Properties", Qt.RightToolBarArea)
    props_toolbar.setObjectName("PropsToolbar")
    
    # Insert a break before the properties toolbar
    main_window.insertToolBarBreak(props_toolbar)
    
    # Now props_toolbar should be in a new column
    
    # Add actions to toolbars
    def add_toolbar_actions():
        """Add sample actions to toolbars for testing."""
        # File toolbar
        new_action = QAction("New", main_window)
        new_action.triggered.connect(lambda: status_bar.showMessage("New action triggered", 2000))
        file_toolbar.addAction(new_action)
        
        open_action = QAction("Open", main_window)
        open_action.triggered.connect(lambda: status_bar.showMessage("Open action triggered", 2000))
        file_toolbar.addAction(open_action)
        
        # Edit toolbar
        copy_action = QAction("Copy", main_window)
        copy_action.triggered.connect(lambda: status_bar.showMessage("Copy action triggered", 2000))
        edit_toolbar.addAction(copy_action)
        
        paste_action = QAction("Paste", main_window)
        paste_action.triggered.connect(lambda: status_bar.showMessage("Paste action triggered", 2000))
        edit_toolbar.addAction(paste_action)
        
        # Tools toolbar
        hammer_action = QAction("Hammer", main_window)
        hammer_action.triggered.connect(lambda: status_bar.showMessage("Hammer tool selected", 2000))
        tools_toolbar.addAction(hammer_action)
        
        # More actions can be added as needed...
    
    add_toolbar_actions()
    
    # === Menu system for testing toolbar functionality ===
    
    # File menu with save/load for persistence testing
    file_menu = menu_bar.addMenu("File")
    
    save_layout_action = QAction("Save Layout", main_window)
    def save_layout():
        try:
            layout_data = manager.save_layout_to_bytearray()
            with open("toolbar_demo_layout.bin", "wb") as f:
                f.write(layout_data)
            status_bar.showMessage("Layout saved successfully!", 3000)
            print("Layout saved to toolbar_demo_layout.bin")
        except Exception as e:
            status_bar.showMessage(f"Save failed: {e}", 3000)
            print(f"Save error: {e}")
    save_layout_action.triggered.connect(save_layout)
    file_menu.addAction(save_layout_action)
    
    load_layout_action = QAction("Load Layout", main_window)
    def load_layout():
        try:
            with open("toolbar_demo_layout.bin", "rb") as f:
                layout_data = f.read()
            manager.load_layout_from_bytearray(layout_data)
            status_bar.showMessage("Layout loaded successfully!", 3000)
            print("Layout loaded from toolbar_demo_layout.bin")
        except FileNotFoundError:
            status_bar.showMessage("No saved layout found", 3000)
            print("No layout file found")
        except Exception as e:
            status_bar.showMessage(f"Load failed: {e}", 3000)
            print(f"Load error: {e}")
    load_layout_action.triggered.connect(load_layout)
    file_menu.addAction(load_layout_action)
    
    file_menu.addSeparator()
    
    exit_action = QAction("Exit", main_window)
    exit_action.triggered.connect(app.quit)
    file_menu.addAction(exit_action)
    
    # Toolbar menu for testing new API methods
    toolbar_menu = menu_bar.addMenu("Toolbar Tests")
    
    def test_toolbar_area():
        """Test toolBarArea method."""
        results = []
        for toolbar in main_window.toolBars():
            area = main_window.toolBarArea(toolbar)
            area_name = {
                Qt.TopToolBarArea: "Top",
                Qt.BottomToolBarArea: "Bottom", 
                Qt.LeftToolBarArea: "Left",
                Qt.RightToolBarArea: "Right"
            }.get(area, "Unknown")
            results.append(f"{toolbar.windowTitle()}: {area_name}")
        
        message = "Toolbar Areas: " + ", ".join(results)
        status_bar.showMessage(message, 5000)
        print(message)
    
    area_test_action = QAction("Test Toolbar Areas", main_window)
    area_test_action.triggered.connect(test_toolbar_area)
    toolbar_menu.addAction(area_test_action)
    
    def test_toolbar_breaks():
        """Test toolBarBreak method."""
        results = []
        for toolbar in main_window.toolBars():
            has_break = main_window.toolBarBreak(toolbar)
            results.append(f"{toolbar.windowTitle()}: {'Break' if has_break else 'No break'}")
        
        message = "Toolbar Breaks: " + ", ".join(results)
        status_bar.showMessage(message, 5000)
        print(message)
    
    break_test_action = QAction("Test Toolbar Breaks", main_window)
    break_test_action.triggered.connect(test_toolbar_breaks)
    toolbar_menu.addAction(break_test_action)
    
    def add_dynamic_toolbar():
        """Test dynamic toolbar addition."""
        new_toolbar = main_window.addToolBar("Dynamic Toolbar")
        new_toolbar.setObjectName("DynamicToolbar")
        
        test_action = QAction("Dynamic Action", main_window)
        test_action.triggered.connect(lambda: status_bar.showMessage("Dynamic action executed!", 2000))
        new_toolbar.addAction(test_action)
        
        status_bar.showMessage("Dynamic toolbar added to top area", 2000)
    
    add_dynamic_action = QAction("Add Dynamic Toolbar", main_window)
    add_dynamic_action.triggered.connect(add_dynamic_toolbar)
    toolbar_menu.addAction(add_dynamic_action)
    
    # Help menu
    help_menu = menu_bar.addMenu("Help")
    
    about_action = QAction("About", main_window)
    def show_about():
        about_text = ("JCDock Enhanced Toolbar Demo v1.0\\n\\n"
                     "Features demonstrated:\\n"
                     "• Multiple toolbar rows/columns with breaks\\n"
                     "• Toolbar insertion and positioning\\n" 
                     "• Complete toolbar persistence\\n"
                     "• Full QMainWindow-like API compatibility")
        print(about_text.replace("\\n", "\n"))
        status_bar.showMessage("JCDock Enhanced Toolbar Demo v1.0", 3000)
    about_action.triggered.connect(show_about)
    help_menu.addAction(about_action)
    
    # Create initial demo widget
    content = create_content_widget(1)
    demo_container = manager.create_window(
        content,
        title="Demo Widget",
        x=300, y=250, width=300, height=200
    )
    demo_container.show()
    
    # Show main window
    main_window.show()
    
    print("\nEnhanced Toolbar Demo Instructions:")
    print("1. Observe multiple toolbar rows in top area (due to breaks)")
    print("2. Note multiple toolbar columns in left area") 
    print("3. See toolbar insertion (Info toolbar inserted before Status)")
    print("4. Properties toolbar should be in separate column (break inserted)")
    print("5. Use 'Toolbar Tests' menu to test new API methods")
    print("6. Use 'File > Save/Load Layout' to test toolbar persistence")
    print("7. Try adding dynamic toolbars and test save/load")
    print("8. Right-click on main window for toolbar visibility toggles")
    
    # Run the application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())