"""
Save/Load Demo - JCDock Simple Example

This script demonstrates:
- Widget registration using @dockable decorator
- Layout persistence (save/load functionality)
- Basic widget content without complex state management

Shows how to save and restore container layouts and widget positions.
"""

import sys
import os
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                               QPushButton, QMenuBar)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from JCDock.core.docking_manager import DockingManager
from JCDock.widgets.dock_container import DockContainer
from JCDock import persistable


@persistable("note_widget", "Note Widget")
class NoteWidget(QWidget):
    """A simple note widget for demonstration."""
    
    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("Note Widget")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #2c3e50; padding: 10px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Content
        content_label = QLabel("This is a simple note widget.\nLayout position will be saved/restored.")
        content_label.setStyleSheet("color: #666; padding: 10px;")
        content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_label.setWordWrap(True)
        layout.addWidget(content_label)
        
        # Button
        button = QPushButton("Click Me!")
        button.clicked.connect(lambda: print("Note widget button clicked!"))
        layout.addWidget(button)


@persistable("task_widget", "Task Widget")
class TaskWidget(QWidget):
    """A simple task widget for demonstration."""
    
    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("Task Widget")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #2c3e50; padding: 10px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Content
        content_label = QLabel("This widget shows task information.\nDock position will be saved/restored.")
        content_label.setStyleSheet("color: #666; padding: 10px;")
        content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_label.setWordWrap(True)
        layout.addWidget(content_label)
        
        # Button
        button = QPushButton("Mark Complete")
        button.clicked.connect(lambda: print("Task marked complete!"))
        layout.addWidget(button)


def main():
    # Create the Qt application
    app = QApplication(sys.argv)
    
    # Create the docking manager
    manager = DockingManager()
    
    # Create main window using unified API
    main_window = manager.create_window(
        is_main_window=True,
        title="JCDock Save/Load Demo",
        x=100, y=100, width=600, height=400,
        auto_persistent_root=True
    )
    main_window.setObjectName("MainWindow")
    
    # Add menu bar with save/load functionality
    menu_bar = QMenuBar(main_window)
    main_window.layout().insertWidget(1, menu_bar)
    
    # File menu
    file_menu = menu_bar.addMenu("File")
    
    save_action = QAction("Save Layout", main_window)
    load_action = QAction("Load Layout", main_window)
    file_menu.addAction(save_action)
    file_menu.addAction(load_action)
    file_menu.addSeparator()
    
    exit_action = QAction("Exit", main_window)
    exit_action.triggered.connect(app.quit)
    file_menu.addAction(exit_action)
    
    # Widgets menu
    widgets_menu = menu_bar.addMenu("Widgets")
    
    create_note_action = QAction("Create Note Widget", main_window)
    create_task_action = QAction("Create Task Widget", main_window)
    widgets_menu.addAction(create_note_action)
    widgets_menu.addAction(create_task_action)
    
    
    # Layout file path
    layout_file = os.path.join(os.getcwd(), "demo_layout.bin")
    
    def save_layout():
        """Save current layout to file."""
        try:
            layout_data = manager.save_layout_to_bytearray()
            with open(layout_file, 'wb') as f:
                f.write(layout_data)
            print(f"Layout saved to: {layout_file}")
        except Exception as e:
            print(f"Error saving layout: {e}")
    
    def load_layout():
        """Load layout from file."""
        try:
            if os.path.exists(layout_file):
                with open(layout_file, 'rb') as f:
                    layout_data = f.read()
                manager.load_layout_from_bytearray(layout_data)
                print(f"Layout loaded from: {layout_file}")
            else:
                print(f"Layout file not found: {layout_file}")
        except Exception as e:
            print(f"Error loading layout: {e}")
    
    def create_note_widget():
        """Create a new note widget."""
        note_content = NoteWidget()
        container = manager.create_window(
            note_content,
            key="note_widget",
            title="Note Widget",
            persist=True
        )
        container.show()
        print("Created note widget")
    
    def create_task_widget():
        """Create a new task widget."""
        task_content = TaskWidget()
        container = manager.create_window(
            task_content,
            key="task_widget", 
            title="Task Widget",
            persist=True
        )
        container.show()
        print("Created task widget")
    
    # Connect menu actions
    save_action.triggered.connect(save_layout)
    load_action.triggered.connect(load_layout)
    create_note_action.triggered.connect(create_note_widget)
    create_task_action.triggered.connect(create_task_widget)
    
    # Create initial widgets to demonstrate functionality
    create_note_widget()
    create_task_widget()
    
    # Show main window
    main_window.show()
    
    print("\nSave/Load Demo Instructions:")
    print("1. Use File > Save Layout to save current layout")
    print("2. Use File > Load Layout to restore saved layout")
    print("3. Use Widgets menu to create additional widgets")
    print("4. Dock floating widgets to main window by dragging tabs")
    print("5. Drag tabs outside to create floating windows")
    print("6. Arrange widgets, save layout, then load to see persistence")
    
    # Run the application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())