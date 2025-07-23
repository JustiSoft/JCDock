# JCDock

A flexible and customizable docking framework for PySide6 applications, inspired by modern IDEs.

JCDock allows you to create complex user interfaces where widgets can be docked into containers, undocked into floating windows, and rearranged dynamically by the user through an intuitive drag-and-drop interface.

## Features

* **Advanced Docking**: Dock widgets to the top, bottom, left, right, or center of other widgets and containers with visual overlay guides.
* **Floating Windows**: Undock any widget or group of widgets into its own floating window with native-like appearance including drop shadows and proper window management.
* **Tearable Tabs**: Users can tear individual tabs away from a tab group to instantly create new floating windows with smooth visual feedback.
* **Persistent Layouts**: Save and restore complete application layouts with automatic widget recreation through factory patterns.
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
git clone https://github.com/jcook5376/JCDock.git

# 2. Navigate into the cloned directory
cd JCDock

# 3. Install in "editable" mode
pip install -e .
```

Using the `-e` or `--editable` flag is recommended. It installs the package by creating a link to the source code, so any future updates you pull from the git repository will be immediately reflected in your environment.

***
## Architecture Overview

JCDock uses a unified window model where all floating windows are `DockContainer` instances. The key components are:

- **DockingManager**: Central orchestrator managing all docking operations, widget registration, and layout persistence
- **DockPanel**: Wrapper for any QWidget to make it dockable with title bars and controls  
- **DockContainer**: Advanced host containers with drag-and-drop capabilities and tab/splitter management
- **MainDockWindow**: Main application window with built-in central dock area
- **TearableTabWidget**: Enhanced tab widget supporting drag-out operations with visual feedback

## Basic Usage

Here's a simple example showing how to create a docking application:

```python
import sys
from PySide6.QtWidgets import QApplication, QLabel, QTextEdit
from PySide6.QtCore import Qt

from JCDock.docking_manager import DockingManager
from JCDock.dock_panel import DockPanel
from JCDock.main_dock_window import MainDockWindow

def create_sample_content(name):
    """Create sample content for demonstration."""
    if "text" in name.lower():
        widget = QTextEdit()
        widget.setPlaceholderText(f"Content for {name}")
        return widget
    else:
        label = QLabel(f"{name} Content")
        label.setAlignment(Qt.AlignCenter)
        return label

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 1. Create the Docking Manager
    manager = DockingManager()
    
    # 2. Create the Main Window (includes central dock area)
    main_window = MainDockWindow(manager)
    manager.set_main_window(main_window)
    manager.register_dock_area(main_window.dock_area)

    # 3. Create DockPanel widgets with content
    notes_panel = DockPanel("Notes", manager=manager, persistent_id="notes_widget")
    notes_panel.setContent(create_sample_content("Text Editor"))
    manager.register_widget(notes_panel)

    project_panel = DockPanel("Project Files", manager=manager, persistent_id="project_widget")  
    project_panel.setContent(create_sample_content("Project Explorer"))
    manager.register_widget(project_panel)

    console_panel = DockPanel("Console", manager=manager, persistent_id="console_widget")
    console_panel.setContent(create_sample_content("Console Output"))
    manager.register_widget(console_panel)

    # 4. Set up initial layout programmatically
    manager.dock_widget(project_panel, main_window.dock_area, "left")
    manager.dock_widget(notes_panel, project_panel, "center")  # Creates tab group
    manager.dock_widget(console_panel, main_window.dock_area, "bottom")

    # 5. Optional: Connect to signals for layout change notifications
    def on_layout_changed():
        print("Layout changed!")
        
    manager.signals.layout_changed.connect(on_layout_changed)

    main_window.setGeometry(100, 100, 1200, 800)
    main_window.show()

    sys.exit(app.exec())
```

## Advanced Features

### Widget Factory for Layout Persistence

To support saving and restoring layouts, provide a widget factory function:

```python
def widget_factory(node_data: dict) -> DockPanel:
    """Factory function to recreate widgets during layout restoration."""
    persistent_id = node_data.get('id')
    title = node_data.get('title', 'Restored Widget')
    
    # Create widget based on persistent_id
    widget = DockPanel(title, manager=manager, persistent_id=persistent_id)
    widget.setContent(create_sample_content(title))
    
    return widget

# Register the factory with the manager
manager.set_widget_factory(widget_factory)

# Save and restore layouts
manager.save_layout("my_layout.json")
manager.load_layout("my_layout.json")
```

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
```

***
## License

This project is licensed under the MIT License - see the LICENSE file for details.