# JCDock

A flexible and customizable docking framework for PySide6 applications, inspired by modern IDEs.

JCDock allows you to create complex user interfaces where widgets can be docked into containers, undocked into floating windows, and rearranged dynamically by the user through an intuitive drag-and-drop interface.

## Features

* **Advanced Docking**: Dock widgets to the top, bottom, left, right, or center of other widgets and containers with visual overlay guides.
* **Floating Windows**: Undock any widget or group of widgets into its own floating window with native-like appearance including drop shadows and proper window management.
* **Tearable Tabs**: Users can tear individual tabs away from a tab group to instantly create new floating windows with smooth visual feedback.
* **Persistent Layouts**: Save and restore complete application layouts with automatic widget recreation through the registry system.
* **Nested Splitters**: Automatically create and manage complex nested horizontal and vertical splitter layouts.
* **Multi-Monitor Support**: Full support for dragging and docking across multiple monitors with proper coordinate handling.
* **Performance Optimized**: Built-in caching systems for icons and hit-testing to ensure smooth performance even with complex layouts.
* **Customizable Appearance**: Easily customize title bar colors, widget styling, and visual effects.
* **Signal System**: Comprehensive event system to track widget docking, undocking, and layout changes.
* **Floating Dock Roots**: Create multiple independent floating windows that can act as primary docking targets.

***
## Installation

**Note:** This library is currently under active development and has not been published to a package repository like PyPI. The only way to install it is directly from GitHub.

To use JCDock in your project, you'll need to clone the source code and install it locally using pip.

```bash
# 1. Clone the repository from GitHub
git clone https://github.com/JustiSoft/JCDock.git

# 2. Navigate into the cloned directory
cd JCDock

# 3. Install in "editable" mode
pip install -e .
```

Using the `-e` or `--editable` flag is recommended. It installs the package by creating a link to the source code, so any future updates you pull from the git repository will be immediately reflected in your environment.

***
## Architecture Overview

JCDock uses a unified window model where all floating windows are `DockContainer` instances. The architecture is built around a central state machine with specialized components:

### Core Components
- **DockingManager**: Central orchestrator managing all docking operations, widget registration, and layout persistence
- **DockingState**: State machine defining operational states (IDLE, RENDERING, DRAGGING_WINDOW, RESIZING_WINDOW, DRAGGING_TAB)
- **DockPanel**: Wrapper for any QWidget to make it dockable with title bars and controls  
- **DockContainer**: Advanced host containers with drag-and-drop capabilities and tab/splitter management
- **MainDockWindow**: Main application window with built-in central dock area
- **TearableTabWidget**: Enhanced tab widget supporting drag-out operations with visual feedback

### Specialized Systems
- **LayoutSerializer**: Handles serialization and deserialization of dock layout state
- **DragDropController**: Manages drag-and-drop operations and visual feedback
- **LayoutRenderer**: Handles layout rendering and state transitions
- **WidgetRegistry**: Registry system for widget types enabling automatic layout persistence
- **HitTestCache**: Performance optimization for overlay hit-testing during drag operations
- **IconCache**: LRU cache system for icon rendering performance optimization

## Basic Usage

Here's the simplest possible example showing how to create a floating dockable widget:

```python
import sys
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import Qt

from JCDock.docking_manager import DockingManager

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 1. Create the Docking Manager
    manager = DockingManager()
    
    # 2. Create content and make it a floating dockable widget
    content = QLabel("Hello, JCDock!")
    content.setAlignment(Qt.AlignCenter)
    manager.create_simple_floating_widget(content, "My Widget")

    sys.exit(app.exec())
```

### Creating a Main Window with Docking

For a more complete application with a main window and multiple dockable widgets:

```python
import sys
from PySide6.QtWidgets import QApplication, QLabel, QTextEdit
from PySide6.QtCore import Qt

from JCDock.docking_manager import DockingManager
from JCDock.main_dock_window import MainDockWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 1. Create the Docking Manager
    manager = DockingManager()
    
    # 2. Create the Main Window (automatically handles registration)
    main_window = MainDockWindow(manager)

    # 3. Create simple floating widgets
    project_content = QLabel("Project Explorer")
    _, project_panel = manager.create_simple_floating_widget(project_content, "Project")

    editor_content = QTextEdit("Your code here...")
    _, editor_panel = manager.create_simple_floating_widget(editor_content, "Editor")

    # 4. Dock widgets to create layout
    manager.dock_widget(project_panel, main_window.dock_area, "left")
    manager.dock_widget(editor_panel, project_panel, "right")

    main_window.setGeometry(100, 100, 1000, 600)
    main_window.show()

    sys.exit(app.exec())
```

## Complete Examples

For a comprehensive demonstration of JCDock's capabilities and different API usage patterns, refer to the complete example script at `src/JCDock/Examples/dock_test.py`. This script showcases:

- **Registry-based widget creation** using `@dockable` decorators
- **Both API paths**: "By Type" (registry-based) and "By Instance" (existing widgets)
- **Layout persistence** with save/load functionality
- **Comprehensive testing functions** for all API methods including widget finding, listing, docking operations, and state management
- **Signal system usage** with event listeners for layout changes
- **Interactive menu system** for testing different features and operations

This example serves as both a testing framework and a reference implementation, showing various ways to integrate JCDock into your applications.

## Advanced Features

### Layout Persistence

JCDock automatically supports saving and restoring layouts when you use the registry system with `@dockable` decorated widgets:

```python
from JCDock import dockable

# Register widget types for automatic layout persistence
@dockable("project_explorer", "Project Explorer")
class ProjectWidget(QLabel):
    def __init__(self):
        super().__init__()
        self.setText("Project Files")

@dockable("code_editor", "Code Editor")
class EditorWidget(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setPlainText("# Your code here")

# Create widgets using registry keys
manager.create_floating_widget_from_key("project_explorer")
manager.create_floating_widget_from_key("code_editor")

# Save and restore layouts (binary format)
layout_data = manager.save_layout_to_bytearray()

# Later, restore the exact same layout
manager.load_layout_from_bytearray(layout_data)
```

The registry system automatically handles widget recreation during layout restoration - no manual factory functions needed!

### Signal System

Connect to docking events to respond to layout changes:

```python
# Connect to various signals
manager.signals.widget_docked.connect(lambda widget, container: 
    print(f"Widget '{widget.windowTitle()}' docked"))
    
manager.signals.widget_undocked.connect(lambda widget: 
    print(f"Widget '{widget.windowTitle()}' undocked"))
    
manager.signals.widget_closed.connect(lambda persistent_id: 
    print(f"Widget '{persistent_id}' closed"))

manager.signals.layout_changed.connect(lambda: 
    print("Layout changed - save state, update UI, etc."))
```

**Available Signals:**
- `widget_docked(widget, container)` - Widget docked into a container
- `widget_undocked(widget)` - Widget undocked to floating window  
- `widget_closed(persistent_id)` - Widget closed and removed
- `layout_changed()` - Any layout modification occurred

***
## License

This project is licensed under the MIT License - see the LICENSE file for details.