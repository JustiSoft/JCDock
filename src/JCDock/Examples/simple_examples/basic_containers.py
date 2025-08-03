"""
Basic Containers Demo - JCDock Simple Example

This script demonstrates the simplest JCDock setup:
- Creating floating widgets using create_window()
- Basic docking operations between widgets
- No registration system needed - just simple QWidget content

This is the most basic example showing JCDock's core widget-to-widget docking.
"""

import sys
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget
from PySide6.QtCore import Qt
from JCDock.core.docking_manager import DockingManager


def main():
    # Create the Qt application
    app = QApplication(sys.argv)
    
    # Create the docking manager
    manager = DockingManager()
    
    # Create simple content widgets
    content1 = QLabel("Simple Content Widget 1")
    content1.setAlignment(Qt.AlignmentFlag.AlignCenter)
    content1.setStyleSheet("background-color: #e8f4f8; padding: 20px; font-size: 14px;")
    
    content2 = QWidget()
    layout2 = QVBoxLayout(content2)
    layout2.addWidget(QLabel("Content Widget 2"))
    button = QPushButton("Click me!")
    button.clicked.connect(lambda: print("Button clicked in widget 2!"))
    layout2.addWidget(button)
    
    # Create floating containers using the unified method
    container1 = manager.create_window(
        content1, 
        title="First Widget", 
        x=100, y=100, width=300, height=200
    )
    
    container2 = manager.create_window(
        content2,
        title="Second Widget",
        x=450, y=100, width=300, height=200
    )
    
    # Show both containers
    container1.show()
    container2.show()
    
    print("\nBasic Containers Demo Instructions:")
    print("1. Two floating widgets are created")
    print("2. Drag one widget's tab to the other widget to dock them together")
    print("3. Drag tabs out to undock them back to floating state")
    print("4. Try dragging by the title bar to move entire windows")
    
    # Run the application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())