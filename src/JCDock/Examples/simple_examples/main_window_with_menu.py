"""
Main Window with Menu Demo - JCDock Simple Example

This script demonstrates:
- Creating a main application window using create_window()
- Adding a menu bar to the main window  
- Creating simple content widgets using create_window()
- Basic menu structure for a JCDock application

Shows how to set up a main window with menu bar as the foundation for a JCDock app.
"""

import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QMenuBar
from PySide6.QtGui import QAction
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
    content = QLabel(f"This is widget {widget_num}.\nDrag this tab to dock with other widgets.")
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
        title="JCDock Main Window Demo",
        x=200, y=200, width=600, height=400,
        auto_persistent_root=True
    )
    main_window.setObjectName("MainWindow")
    
    # Add menu bar
    menu_bar = QMenuBar(main_window)
    main_window.layout().insertWidget(1, menu_bar)
    
    # File menu
    file_menu = menu_bar.addMenu("File")
    exit_action = QAction("Exit", main_window)
    exit_action.triggered.connect(app.quit)
    file_menu.addAction(exit_action)
    
    # Widgets menu  
    widgets_menu = menu_bar.addMenu("Widgets")
    
    create_action = QAction("Create Widget", main_window)
    widgets_menu.addAction(create_action)
    
    # Help menu
    help_menu = menu_bar.addMenu("Help")
    about_action = QAction("About", main_window)
    about_action.triggered.connect(lambda: print("JCDock Main Window Demo v1.0"))
    help_menu.addAction(about_action)
    
    # Widget counter for unique names
    widget_counter = 0
    
    def create_floating_widget():
        """Create a new floating widget."""
        nonlocal widget_counter
        widget_counter += 1
        
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
    
    # Connect menu action
    create_action.triggered.connect(create_floating_widget)
    
    # Create initial widget to demonstrate
    create_floating_widget()
    
    # Show main window
    main_window.show()
    
    print("\nMain Window Demo Instructions:")
    print("1. Use 'Widgets > Create Widget' to create new floating widgets")
    print("2. Drag tabs between windows to dock widgets together")
    print("3. Use title bars to move entire windows")
    print("4. This shows basic main window setup with menu bar")
    
    # Run the application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())