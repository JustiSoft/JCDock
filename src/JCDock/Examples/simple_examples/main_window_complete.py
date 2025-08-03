"""
Complete Main Window Demo - JCDock Simple Example

This script demonstrates:
- Creating a main application window using create_window()
- Adding a menu bar to the main window  
- Adding a status bar to the main window
- Adding multiple toolbars to different areas
- Creating simple content widgets using create_window()
- Complete QMainWindow-like interface for a JCDock application

Shows how to set up a fully-featured main window with menu bar, status bar, and toolbars.
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
    title = QLabel(f"Content Widget {widget_num}")
    title.setStyleSheet("font-weight: bold; font-size: 16px; color: #2c3e50; padding: 10px;")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)
    
    # Content
    content = QLabel(f"This is widget {widget_num}.\nDrag this tab to dock with other widgets.\nUse toolbars to interact with widgets.")
    content.setStyleSheet("color: #666; padding: 10px;")
    content.setAlignment(Qt.AlignmentFlag.AlignCenter)
    content.setWordWrap(True)
    layout.addWidget(content)
    
    # Button
    button = QPushButton(f"Action {widget_num}")
    button.clicked.connect(lambda: print(f"Action {widget_num} executed!"))
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
        title="JCDock Complete Main Window Demo",
        x=200, y=200, width=800, height=600,
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
    status_bar.showMessage("Ready - Complete main window with toolbars, menu, and status bar")
    
    # Add toolbars
    # Top toolbar - File operations
    file_toolbar = main_window.addToolBar("File Toolbar")
    file_toolbar.setToolTip("File operations")
    
    # Bottom toolbar - Status and info
    info_toolbar = main_window.addToolBar("Info Toolbar", Qt.BottomToolBarArea)
    info_toolbar.setToolTip("Information and status")
    
    # Left toolbar - Tools (vertical)
    tools_toolbar = main_window.addToolBar("Tools Toolbar", Qt.LeftToolBarArea)
    tools_toolbar.setToolTip("Tools and utilities")
    
    # Create File menu
    file_menu = menu_bar.addMenu("File")
    
    # Widget counter for unique names
    widget_counter = 0
    
    def create_floating_widget():
        """Create a new floating widget."""
        nonlocal widget_counter
        widget_counter += 1
        
        status_bar.showMessage(f"Creating widget {widget_counter}...")
        
        content = create_content_widget(widget_counter)
        container = manager.create_window(
            content,
            title=f"Widget {widget_counter}",
            x=300 + (widget_counter * 30), 
            y=250 + (widget_counter * 30),
            width=300, height=200
        )
        container.show()
        print(f"Created widget {widget_counter}")
        
        status_bar.showMessage(f"Ready - {widget_counter} widgets created")
        
        # Update info toolbar
        update_info_toolbar()
    
    def update_info_toolbar():
        """Update the info toolbar with current stats."""
        info_toolbar.clear()
        info_label = QLabel(f"Widgets: {widget_counter}")
        info_label.setStyleSheet("padding: 5px; color: #333;")
        info_toolbar.addWidget(info_label)
    
    def close_all_widgets():
        """Close all floating widgets."""
        nonlocal widget_counter
        for container in manager.containers.copy():
            if container != main_window:
                container.close()
        widget_counter = 0
        status_bar.showMessage("All widgets closed")
        update_info_toolbar()
    
    def show_toolbar_info():
        """Show information about toolbars."""
        toolbar_count = len(main_window.toolBars())
        top_toolbars = len(main_window.toolBars(Qt.TopToolBarArea))
        bottom_toolbars = len(main_window.toolBars(Qt.BottomToolBarArea))
        left_toolbars = len(main_window.toolBars(Qt.LeftToolBarArea))
        
        info = f"Toolbars: {toolbar_count} total (Top: {top_toolbars}, Bottom: {bottom_toolbars}, Left: {left_toolbars})"
        status_bar.showMessage(info, 5000)
        print(info)
    
    # File toolbar actions
    new_action = QAction("New Widget", main_window)
    new_action.setToolTip("Create a new floating widget")
    new_action.triggered.connect(create_floating_widget)
    file_toolbar.addAction(new_action)
    
    file_toolbar.addSeparator()
    
    close_all_action = QAction("Close All", main_window)
    close_all_action.setToolTip("Close all floating widgets")
    close_all_action.triggered.connect(close_all_widgets)
    file_toolbar.addAction(close_all_action)
    
    # Tools toolbar actions
    info_action = QAction("Toolbar Info", main_window)
    info_action.setToolTip("Show toolbar information")
    info_action.triggered.connect(show_toolbar_info)
    tools_toolbar.addAction(info_action)
    
    tools_toolbar.addSeparator()
    
    # Add a toggle action for demonstration
    def toggle_bottom_toolbar():
        info_toolbar.setVisible(not info_toolbar.isVisible())
        status_bar.showMessage(f"Bottom toolbar {'shown' if info_toolbar.isVisible() else 'hidden'}")
    
    toggle_action = QAction("Toggle Bottom Toolbar", main_window)
    toggle_action.setToolTip("Show/hide bottom toolbar")
    toggle_action.triggered.connect(toggle_bottom_toolbar)
    tools_toolbar.addAction(toggle_action)
    
    # File menu actions
    new_menu_action = QAction("New Widget", main_window)
    new_menu_action.triggered.connect(create_floating_widget)
    file_menu.addAction(new_menu_action)
    
    file_menu.addSeparator()
    
    exit_action = QAction("Exit", main_window)
    exit_action.triggered.connect(app.quit)
    file_menu.addAction(exit_action)
    
    # View menu for toolbar management
    view_menu = menu_bar.addMenu("View")
    
    toolbar_menu = view_menu.addMenu("Toolbars")
    
    # Add toolbar visibility toggles
    file_toolbar_action = QAction("File Toolbar", main_window)
    file_toolbar_action.setCheckable(True)
    file_toolbar_action.setChecked(True)
    file_toolbar_action.triggered.connect(lambda checked: file_toolbar.setVisible(checked))
    toolbar_menu.addAction(file_toolbar_action)
    
    info_toolbar_action = QAction("Info Toolbar", main_window)
    info_toolbar_action.setCheckable(True)
    info_toolbar_action.setChecked(True)
    info_toolbar_action.triggered.connect(lambda checked: info_toolbar.setVisible(checked))
    toolbar_menu.addAction(info_toolbar_action)
    
    tools_toolbar_action = QAction("Tools Toolbar", main_window)
    tools_toolbar_action.setCheckable(True)
    tools_toolbar_action.setChecked(True)
    tools_toolbar_action.triggered.connect(lambda checked: tools_toolbar.setVisible(checked))
    toolbar_menu.addAction(tools_toolbar_action)
    
    # Help menu
    help_menu = menu_bar.addMenu("Help")
    about_action = QAction("About", main_window)
    def show_about():
        print("JCDock Complete Main Window Demo v1.0")
        status_bar.showMessage("JCDock Complete Main Window Demo v1.0 - Full QMainWindow-like interface", 3000)
    about_action.triggered.connect(show_about)
    help_menu.addAction(about_action)
    
    # Initialize info toolbar
    update_info_toolbar()
    
    # Create initial widget to demonstrate
    create_floating_widget()
    
    # Show main window
    main_window.show()
    
    print("\nComplete Main Window Demo Instructions:")
    print("1. Use toolbar buttons or 'File > New Widget' to create widgets")
    print("2. Drag tabs between windows to dock widgets together")
    print("3. Use 'View > Toolbars' to show/hide toolbars")
    print("4. Use 'Tools Toolbar' to get toolbar information")
    print("5. Watch the status bar and info toolbar for real-time updates")
    print("6. This demonstrates full QMainWindow-like functionality in JCDock")
    
    # Run the application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())