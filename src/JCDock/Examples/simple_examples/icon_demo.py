"""
Icon Demo - JCDock Simple Example

This script demonstrates:
- Creating floating widgets using create_simple_floating_widget()
- Setting icons on dock panels using panel.set_icon()
- Using Qt standard icons for different widget types
- Icon persistence through docking operations

Shows how icons appear in both title bars and tabs during drag operations.
"""

import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from JCDock.core.docking_manager import DockingManager
from JCDock.widgets.dock_container import DockContainer


def create_icon_widget(title: str, description: str) -> QWidget:
    """Create a simple widget for icon demonstration."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    
    # Title
    title_label = QLabel(title)
    title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50; padding: 10px;")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title_label)
    
    # Description
    desc_label = QLabel(description)
    desc_label.setStyleSheet("color: #666; padding: 5px;")
    desc_label.setWordWrap(True)
    layout.addWidget(desc_label)
    
    return widget


def main():
    # Create the Qt application
    app = QApplication(sys.argv)
    
    # Create the docking manager
    manager = DockingManager()
    
    # Create main container with an icon using unified API
    main_container = manager.create_window(
        is_main_window=True,
        title="Icon Demo - Main Container",
        x=100, y=100, width=500, height=350
    )
    main_container.setObjectName("MainContainer")
    
    # Set icon on main container
    main_icon = app.style().standardIcon(app.style().StandardPixmap.SP_DesktopIcon)
    main_container.set_icon(main_icon)
    
    # Widget 1: Computer Icon
    content1 = create_icon_widget(
        "Computer Widget",
        "This widget uses SP_ComputerIcon.\nDrag this tab to test icon persistence."
    )
    
    # Set computer icon
    computer_icon = app.style().standardIcon(app.style().StandardPixmap.SP_ComputerIcon)
    
    container1 = manager.create_window(
        content1,
        title="Computer Widget",
        x=150, y=150, width=300, height=180,
        icon=computer_icon
    )
    
    # Widget 2: Folder Icon
    content2 = create_icon_widget(
        "Folder Widget",
        "This widget uses SP_DirOpenIcon.\nNotice how icons appear in tabs and title bars."
    )
    
    # Set folder icon
    folder_icon = app.style().standardIcon(app.style().StandardPixmap.SP_DirOpenIcon)
    
    container2 = manager.create_window(
        content2,
        title="Folder Widget",
        x=500, y=150, width=300, height=180,
        icon=folder_icon
    )
    
    # Widget 3: File Icon
    content3 = create_icon_widget(
        "File Widget",
        "This widget uses SP_FileIcon.\nDrag between containers to see icon persistence."
    )
    
    # Set file icon
    file_icon = app.style().standardIcon(app.style().StandardPixmap.SP_FileIcon)
    
    container3 = manager.create_window(
        content3,
        title="File Widget",
        x=325, y=400, width=300, height=180,
        icon=file_icon
    )
    
    # Show all containers
    main_container.show()
    container1.show()
    container2.show()
    container3.show()
    
    print("\nIcon Demo Instructions:")
    print("1. Each widget has a different type of icon in its title bar and tab")
    print("2. Drag tabs between containers to see icon persistence")
    print("3. Drag tabs outside containers to create floating windows with icons")
    print("4. Icons appear in both title bars and tab headers")
    print("5. Try docking widgets together to see icons in tab groups")
    
    # Run the application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())