# JCDock

A flexible and customizable docking framework for PySide6 applications, inspired by modern IDEs.

JCDock allows you to create complex user interfaces where widgets can be docked into containers, undocked into floating windows, and rearranged dynamically by the user.

## Features

* **Advanced Docking**: Dock widgets to the top, bottom, left, right, or center of other widgets and containers.
* **Floating Windows**: Undock any widget or group of widgets into its own floating window with a native-like look and feel (including shadows and rounded corners).
* **Tearable Tabs**: Users can tear individual tabs away from a tab group to instantly create a new floating window.
* **Persistent Layouts**: Save the entire state of your application's layout to a file or byte array and restore it later.
* **Nested Splitters**: Automatically create and manage nested horizontal and vertical splitters.
* **Customizable Appearance**: Easily change colors and styles of widgets and title bars.
* **Floating Dock Roots**: Create multiple, independent floating "main windows" that can act as primary docking targets.

***
## Installation

**Note:** This library is currently under active development and has not been published to a package repository like PyPI. The only way to install it is directly from GitHub.

To use JCDock in your project, you'll need to clone the source code and install it locally using pip.

```bash
# 1. Clone the repository from GitHub
git clone https://github.com/jcook5376/JCDock.git

# 2. Navigate into the cloned directory
cd JCDock

# 3. Install in "editable" mode
pip install -e .
```

Using the `-e` or `--editable` flag is recommended. It installs the package by creating a link to the source code, so any future updates you pull from the git repository will be immediately reflected in your environment.

***
## Basic Usage

Here is a simple example of how to set up a main window and a few dockable widgets.

```python
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QTextEdit
from PySide6.QtCore import Qt

# Assume JCDock is installed and its components are in the JCDock package
from JCDock.docking_manager import DockingManager
from JCDock.dockable_widget import DockableWidget
from JCDock.dock_container import DockContainer

# A simple main window to host the central dock area
class MainDockWindow(QMainWindow):
    def __init__(self, manager):
        super().__init__()
        self.setWindowTitle("JCDock Demo")
        self.manager = manager

        # The central widget will be a DockContainer
        self.dock_area = DockContainer(parent=self, manager=self.manager, create_shadow=False, show_title_bar=False)
        self.setCentralWidget(self.dock_area)
        self.manager.set_main_window(self)
        self.manager.register_dock_area(self.dock_area)

```

***
## Main Application Setup
```python
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 1. Create the Docking Manager
    manager = DockingManager()
    manager.set_debug_mode(True) # Optional: for printing layout state

    # 2. Create the Main Window
    main_window = MainDockWindow(manager)

    # 3. Create some content widgets
    notes_content = QTextEdit()
    notes_content.setPlaceholderText("Write your notes here...")

    project_files_content = QLabel("Project Files Placeholder")
    project_files_content.setAlignment(Qt.AlignCenter)

    console_content = QLabel("Console Output Placeholder")
    console_content.setAlignment(Qt.AlignCenter)

    # 4. Wrap content in DockableWidgets
    notes_widget = DockableWidget(title="Notes", manager=manager)
    notes_widget.setContent(notes_content)
    manager.register_widget(notes_widget) # Register it with the manager

    project_widget = DockableWidget(title="Project", manager=manager)
    project_widget.setContent(project_files_content)
    manager.register_widget(project_widget)

    console_widget = DockableWidget(title="Console", manager=manager)
    console_widget.setContent(console_content)
    manager.register_widget(console_widget)

    # 5. Programmatically set up an initial layout
    manager.dock_widget(project_widget, main_window.dock_area, "left")
    manager.dock_widget(notes_widget, project_widget, "center") # Docks as a tab with Project
    manager.dock_widget(console_widget, main_window.dock_area, "bottom")

    main_window.setGeometry(100, 100, 1200, 800)
    main_window.show()

    sys.exit(app.exec())
```

***
## License

This project is licensed under the MIT License - see the LICENSE file for details.