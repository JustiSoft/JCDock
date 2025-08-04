# JCDock

A flexible and customizable docking framework for PySide6 applications, inspired by modern IDEs.

JCDock allows you to create complex user interfaces where widgets can be docked into containers, undocked into floating windows, and rearranged dynamically by the user through an intuitive drag-and-drop interface.

## Features

For detailed API documentation, see the [wiki/](wiki/) directory.

* **Advanced Docking**: Dock widgets to the top, bottom, left, right, or center of other widgets and containers with visual overlay guides.
* **Floating Windows**: Undock any widget or group of widgets into its own floating window with native-like appearance including drop shadows and proper window management.
* **Tearable Tabs**: Users can tear individual tabs away from a tab group to instantly create new floating windows with smooth visual feedback.
* **Persistent Layouts**: Save and restore complete application layouts with automatic widget recreation through the registry system.
* **Nested Splitters**: Automatically create and manage complex nested horizontal and vertical splitter layouts.
* **Multi-Monitor Support**: Full support for dragging and docking across multiple monitors with proper coordinate handling.
* **Performance Optimized**: Built-in caching systems for icons and hit-testing to ensure smooth performance even with complex layouts.
* **Customizable Appearance**: Easily customize title bar colors, widget styling, and visual effects.
* **Signal System**: Comprehensive event system to track widget docking, undocking, and layout changes.
* **Enhanced Toolbar Support**: Create dynamic toolbars with breaks, insertion control, and persistent layouts.
* **Multi-Area Layout**: Support for complex layouts with multiple independent docking areas.

***
## Installation

JCDock is available on PyPI and can be installed using pip. Choose the installation method that best fits your needs:

### Option 1: Install from PyPI (Recommended for Users)

For most users who want to use JCDock in their applications:

```bash
pip install JCDock
```

This installs the latest stable release directly from PyPI.

### Option 2: Install from Source (For Development)

For developers who want to contribute to JCDock or need the latest development features:

```bash
# 1. Clone the repository from GitHub
git clone https://github.com/JustiSoft/JCDock.git

# 2. Navigate into the cloned directory
cd JCDock

# 3. Install in "editable" mode
pip install -e .
```

Using the `-e` or `--editable` flag is recommended for development. It installs the package by creating a link to the source code, so any changes you make to the code will be immediately reflected in your environment.

***
## Architecture Overview

JCDock uses a unified window model where all floating windows are `DockContainer` instances. The architecture is built around a central state machine with specialized components:

### Core Components
- **DockingManager** (`src/JCDock/core/docking_manager.py`): Central orchestrator managing all docking operations, widget registration, and layout persistence
- **DockingState** (`src/JCDock/core/docking_manager.py`): State machine defining operational states (IDLE, RENDERING, DRAGGING_WINDOW, RESIZING_WINDOW, DRAGGING_TAB)
- **DockPanel** (`src/JCDock/widgets/dock_panel.py`): Wrapper for any QWidget to make it dockable with title bars and controls  
- **DockContainer** (`src/JCDock/widgets/dock_container.py`): Unified container system supporting both embedded and floating windows with configurable behavior (main window, persistent root, title bars, etc.)
- **TearableTabWidget** (`src/JCDock/widgets/tearable_tab_widget.py`): Enhanced tab widget supporting drag-out operations with visual feedback

### Specialized Systems

#### Core (`src/JCDock/core/`)
- **WidgetRegistry** (`src/JCDock/core/widget_registry.py`): Registry system for widget types enabling automatic layout persistence
- **DockingState** (`src/JCDock/core/docking_manager.py`): State machine enum defining operational states

#### Model (`src/JCDock/model/`)
- **LayoutSerializer** (`src/JCDock/model/layout_serializer.py`): Handles serialization and deserialization of dock layout state
- **LayoutRenderer** (`src/JCDock/model/layout_renderer.py`): Handles layout rendering and state transitions
- **LayoutModel** (`src/JCDock/model/dock_model.py`): Core data structures for layout representation

#### Interaction (`src/JCDock/interaction/`)
- **DragDropController** (`src/JCDock/interaction/drag_drop_controller.py`): Manages drag-and-drop operations and visual feedback
- **DragProxy** (`src/JCDock/interaction/drag_proxy.py`): Drag preview widgets for visual feedback
- **OverlayManager** (`src/JCDock/interaction/overlay_manager.py`): Manages visual overlay system during drag operations
- **DockingOverlay** (`src/JCDock/interaction/docking_overlay.py`): Visual feedback overlays for drop zones

#### Factories (`src/JCDock/factories/`)
- **WidgetFactory** (`src/JCDock/factories/widget_factory.py`): Creates and manages widget instances
- **WindowManager** (`src/JCDock/factories/window_manager.py`): Handles window creation and management
- **ModelUpdateEngine** (`src/JCDock/factories/model_update_engine.py`): Manages model state updates

#### Utils (`src/JCDock/utils/`)
- **HitTestCache** (`src/JCDock/utils/hit_test_cache.py`): Performance optimization for overlay hit-testing during drag operations
- **IconCache** (`src/JCDock/utils/icon_cache.py`): LRU cache system for icon rendering performance optimization
- **PerformanceMonitor** (`src/JCDock/utils/performance_monitor.py`): Runtime performance tracking and metrics collection
- **ResizeCache** (`src/JCDock/utils/resize_cache.py`): Resize constraint caching and validation
- **ResizeGestureManager** (`src/JCDock/utils/resize_gesture_manager.py`): Advanced resize gesture handling
- **ResizeThrottler** (`src/JCDock/utils/resize_throttler.py`): Throttling system for resize operations
- **WindowsShadow** (`src/JCDock/utils/windows_shadow.py`): Native Windows DWM shadow effects

## Basic Usage

Here's the simplest possible example showing how to create a floating dockable widget:

```python
import sys
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import Qt

from JCDock import DockingManager

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 1. Create the Docking Manager
    manager = DockingManager()
    
    # 2. Create content and make it a floating dockable widget
    content = QLabel("Hello, JCDock!")
    content.setAlignment(Qt.AlignCenter)
    
    window = manager.create_window(
        content=content,
        title="My Widget",
        persist=True
    )
    window.show()

    sys.exit(app.exec())
```

### Creating a Main Window with Docking

For a more complete application with a main window and multiple dockable widgets:

```python
import sys
from PySide6.QtWidgets import QApplication, QLabel, QTextEdit
from PySide6.QtCore import Qt

from JCDock import DockingManager

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 1. Create the Docking Manager
    manager = DockingManager()
    
    # 2. Create a main window
    main_window = manager.create_window(
        title="My Application",
        is_main_window=True,
        persist=True,
        x=100,
        y=100,
        width=1000,
        height=600
    )

    # 3. Create widget content
    project_content = QLabel("Project Explorer")
    editor_content = QTextEdit("Your code here...")
    
    # 4. Register widgets with manager
    manager.register_widget(project_content)
    manager.register_widget(editor_content)

    # 5. Dock widgets to create layout
    manager.dock_widget(project_content, main_window, "left")
    manager.dock_widget(editor_content, main_window, "center")

    main_window.show()

    sys.exit(app.exec())
```

## Complete Examples and Testing

### Comprehensive Test Suite

JCDock includes a modular test suite that demonstrates all framework capabilities and serves as both a testing framework and reference implementation. To run the test suite:

```bash
# From the project root
cd src/JCDock/Examples
../../../.venv/Scripts/python.exe run_test_suite.py
```

![JCDock Demo](src/JCDock/Examples/sample.png)
*Example of JCDock in action showing floating windows, docked panels, and tearable tabs*

The test suite (`src/JCDock/Examples/test_suite/`), which can be run from the Examples directory: provides comprehensive testing through a modular architecture:

#### Core Components
- **Entry Point**: `main.py` for configuration and execution
- **Application Core**: `app.py` handling test orchestration

#### Specialized Managers
- **Test Manager**: Test execution and validation (`managers/test_manager.py`)
- **UI Manager**: Menu system and interaction (`managers/ui_manager.py`)
- **Layout Manager**: Layout persistence testing (`managers/layout_manager.py`)

#### Test Widgets
- **Base Widgets**: Registry and decorator examples (`widgets/test_widgets.py`)
- **Complex Widgets**: Financial dashboard demos (`widgets/financial_widgets.py`)

#### Testing Features
- **Registry Testing**: `@persistable` decorator and widget registration
- **API Coverage**: Both registry and instance-based operations
- **Layout Testing**: Serialization and state preservation
- **Performance**: Visual feedback and drag operation metrics
- **Event System**: Signal listeners and lifecycle events

#### Key Testing Features
- **Registry-based widget creation** using `@persistable` decorators
- **Both API paths**: "By Type" (registry-based) and "By Instance" (existing widgets)
- **Comprehensive testing functions** for all API methods including widget finding, listing, docking operations, and state management
- **Signal system usage** with event listeners for layout changes
- **Interactive menu system** for testing different features and operations
- **Layout persistence testing** with automatic save/load validation
- **Performance monitoring** and drag operation testing

### Layout Persistence

The test suite demonstrates automatic layout persistence using the standard layout file location:

```
layouts/
└── jcdock_layout.ini  # Automatically saved/loaded layout file
└── toolbar_demo_layout.bin  # Example toolbar layout persistence
```

The layout file preserves:
- **Widget positions** and container hierarchies
- **Window geometry** and multi-monitor positioning
- **Widget state** (custom data via `get_dock_state()`/`set_dock_state()`)
- **Tab ordering** and splitter proportions
- **Toolbar layouts** including breaks, insertion points, and custom item states

## Advanced Features

### Layout Persistence

JCDock automatically supports saving and restoring layouts when you use the registry system with `@persistable` decorated widgets:

```python
from PySide6.QtWidgets import QLabel, QTextEdit
from JCDock import persistable

# Register widget types for automatic layout persistence
@persistable("project_explorer", "Project Explorer")
class ProjectWidget(QLabel):
    def __init__(self):
        super().__init__()
        self.setText("Project Files")

@persistable("code_editor", "Code Editor")
class EditorWidget(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setPlainText("# Your code here")

# Create widgets using registered types
project = ProjectWidget()
editor = EditorWidget()

# Create windows for widgets
project_window = manager.create_window(
    content=project,
    key="project_explorer",
    title="Project Explorer",
    persist=True
)

editor_window = manager.create_window(
    content=editor,
    key="code_editor", 
    title="Code Editor",
    persist=True
)

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
## Additional Documentation

- **[wiki/](wiki/)** - Comprehensive API documentation and usage guides
- **CLAUDE.md** - Development guidelines and context for development tools

## License

This project is licensed under the MIT License - see the LICENSE file for details.