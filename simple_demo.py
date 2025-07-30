#!/usr/bin/env python3
"""Simple demo script showcasing JCDock with 5 floating containers."""

import sys
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QTableWidget, QTableWidgetItem, QPushButton, 
                               QLabel, QRadioButton, QButtonGroup, QTextEdit,
                               QListWidget, QProgressBar, QSlider, QSpinBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

# Add the src directory to the path so we can import JCDock
sys.path.insert(0, 'src')

from JCDock.core.docking_manager import DockingManager
from JCDock.widgets.dock_panel import DockPanel
from JCDock.widgets.floating_dock_root import FloatingDockRoot
from JCDock.widgets.dock_container import DockContainer
from JCDock import dockable


def create_table_widget():
    """Create a table widget with sample data."""
    table = QTableWidget(5, 3)
    table.setHorizontalHeaderLabels(['Name', 'Age', 'City'])
    
    data = [
        ['Alice', '25', 'New York'],
        ['Bob', '30', 'Los Angeles'],
        ['Charlie', '35', 'Chicago'],
        ['Diana', '28', 'Miami'],
        ['Eve', '32', 'Seattle']
    ]
    
    for row, row_data in enumerate(data):
        for col, value in enumerate(row_data):
            table.setItem(row, col, QTableWidgetItem(value))
    
    return table


def create_button_widget():
    """Create a widget with various buttons."""
    widget = QWidget()
    widget.setStyleSheet("background-color: lightblue;")
    layout = QVBoxLayout(widget)
    
    layout.addWidget(QLabel("Button Controls"))
    layout.addWidget(QPushButton("Action Button"))
    layout.addWidget(QPushButton("Save"))
    layout.addWidget(QPushButton("Cancel"))
    
    # Radio buttons
    radio_group = QButtonGroup()
    radio1 = QRadioButton("Option 1")
    radio2 = QRadioButton("Option 2") 
    radio3 = QRadioButton("Option 3")
    radio1.setChecked(True)
    
    radio_group.addButton(radio1)
    radio_group.addButton(radio2)
    radio_group.addButton(radio3)
    
    layout.addWidget(QLabel("Choose an option:"))
    layout.addWidget(radio1)
    layout.addWidget(radio2)
    layout.addWidget(radio3)
    
    return widget


def create_text_widget():
    """Create a text editing widget."""
    widget = QWidget()
    widget.setStyleSheet("background-color: lightgreen;")
    layout = QVBoxLayout(widget)
    
    layout.addWidget(QLabel("Text Editor"))
    
    text_edit = QTextEdit()
    text_edit.setPlainText("This is a sample text editor.\n\nYou can type here and edit content.\n\nLorem ipsum dolor sit amet, consectetur adipiscing elit.")
    layout.addWidget(text_edit)
    
    return widget


def create_list_widget():
    """Create a list widget with sample items."""
    widget = QWidget()
    widget.setStyleSheet("background-color: lightyellow;")
    layout = QVBoxLayout(widget)
    
    layout.addWidget(QLabel("Item List"))
    
    list_widget = QListWidget()
    items = ['Item 1', 'Item 2', 'Item 3', 'Important Item', 'Another Item', 'Last Item']
    for item in items:
        list_widget.addItem(item)
    
    layout.addWidget(list_widget)
    
    return widget


def create_controls_widget():
    """Create a widget with various controls."""
    widget = QWidget()
    widget.setStyleSheet("background-color: lightcoral;")
    layout = QVBoxLayout(widget)
    
    layout.addWidget(QLabel("Control Panel"))
    
    # Progress bar
    layout.addWidget(QLabel("Progress:"))
    progress = QProgressBar()
    progress.setValue(65)
    layout.addWidget(progress)
    
    # Slider
    layout.addWidget(QLabel("Volume:"))
    slider = QSlider(Qt.Horizontal)
    slider.setValue(50)
    layout.addWidget(slider)
    
    # Spin box
    layout.addWidget(QLabel("Count:"))
    spinbox = QSpinBox()
    spinbox.setRange(0, 100)
    spinbox.setValue(42)
    layout.addWidget(spinbox)
    
    return widget


def main():
    app = QApplication(sys.argv)
    
    # Create the docking manager first
    manager = DockingManager()
    
    # Create the main window with the manager using FloatingDockRoot
    main_window = FloatingDockRoot(manager=manager, is_main_window=True)
    main_window.setWindowTitle("JCDock Simple Demo")
    main_window.resize(1200, 800)
    main_window.setObjectName("MainDockArea")
    main_window.set_persistent_root(True)
    
    # Hide the title bar since this acts like a main window
    if main_window.title_bar:
        main_window.title_bar.hide()
    
    # Register with the docking manager
    manager.register_dock_area(main_window)
    manager.set_main_window(main_window)
    
    # Create widgets
    widgets = [
        ("Widget 1", create_table_widget()),
        ("Widget 2", create_button_widget()), 
        ("Widget 3", create_text_widget()),
        ("Widget 4", create_list_widget()),
        ("Widget 5", create_controls_widget())
    ]
    
    # Create floating widgets using the simple API
    for i, (title, content_widget) in enumerate(widgets):
        # Position windows in a cascade
        x = 100 + i * 50
        y = 100 + i * 50
        
        # Use the simple API that doesn't require registration
        container, dock_panel = manager.create_simple_floating_widget(
            content_widget, 
            title, 
            x, y, 
            400, 300
        )
    
    # Show the main window
    main_window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())