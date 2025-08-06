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
* **Enhanced Toolbar Support**: Full QMainWindow-style toolbar system with multi-area support (top, bottom, left, right), breaks for row/column organization, precise insertion control, and automatic persistence across sessions.
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
## Simplified Architecture

JCDock uses a **streamlined, single-method architecture** that eliminates complexity while providing full docking capabilities.

### Universal API Design
**One method handles all scenarios:**
```python
manager = DockingManager()

# Main windows, floating widgets, persistent widgets - all use the same method
window = manager.create_window(
    content=widget,      # Any QWidget (optional for main windows)
    title="My Window",
    is_main_window=True, # For main application window
    persist=True,        # For layout persistence
    x=100, y=100, width=400, height=300
)
```

### Key Architecture Benefits
1. **Single Entry Point**: `create_window()` replaces multiple creation methods
2. **Automatic Management**: DockPanel wrapping and DockContainer creation handled internally
3. **Persistent by Design**: `@persistable` decorator + `persist=True` enables layout restoration
4. **User-Friendly**: No need to understand internal component relationships

### Implementation Components (Internal)
- **DockingManager**: Public API facade and central coordinator
- **DockPanel**: Automatic wrapper for making widgets dockable
- **DockContainer**: Internal container implementation for windows
- **Widget Registry**: Automatic widget type management via `@persistable`

### Specialized Systems

### Why This Architecture?

**Before:** Multiple complex methods, manual component management
```python
# Old complex approach (deprecated)
container, panel = manager.create_simple_floating_widget(...)
other_container = manager.create_floating_widget_from_key(...)
manager.register_widget(...)
# Multiple methods, complex relationships
```

**Now:** Single universal method, automatic management
```python
# New streamlined approach
window = manager.create_window(content=widget, title="Widget", persist=True)
# One method, automatic internal management
```

### Internal System Overview (Advanced)
The simplified API is built on a sophisticated internal architecture:

- **State Management**: Coordinated state machine prevents conflicts
- **Performance Optimization**: Automatic caching and throttling systems
- **Layout Persistence**: Binary serialization with widget state preservation
- **Drag & Drop**: Visual overlay system with smooth interactions
- **Multi-Platform**: Native window effects and cross-platform compatibility

### Development Philosophy

JCDock prioritizes **developer experience** over architectural exposure:

1. **Simple API Surface**: One creation method vs. many specialized methods
2. **Automatic Lifecycle**: Internal components managed transparently  
3. **Sensible Defaults**: Minimal configuration required for common scenarios
4. **Progressive Enhancement**: Advanced features available when needed
5. **Future-Proof**: Internal changes don't break application code

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

### Toolbar Integration Example

JCDock provides comprehensive toolbar support with automatic persistence:

```python
import sys
from PySide6.QtWidgets import QApplication, QTextEdit, QToolBar, QAction
from PySide6.QtCore import Qt

from JCDock import DockingManager

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 1. Create the Docking Manager
    manager = DockingManager()
    
    # 2. Create main window with toolbar support
    main_window = manager.create_window(
        title="Text Editor with Toolbars",
        is_main_window=True,
        persist=True,
        width=1000,
        height=600
    )
    
    # 3. Create editor content
    editor = QTextEdit("Start typing...")
    manager.register_widget(editor)
    manager.dock_widget(editor, main_window, "center")
    
    # 4. Add comprehensive toolbar layout
    
    # File operations toolbar
    file_toolbar = main_window.addToolBar("File")
    file_toolbar.addAction("New")
    file_toolbar.addAction("Open")
    file_toolbar.addAction("Save")
    
    # Edit operations toolbar (same row)
    edit_toolbar = main_window.addToolBar("Edit")  
    edit_toolbar.addAction("Cut")
    edit_toolbar.addAction("Copy")
    edit_toolbar.addAction("Paste")
    
    # Create toolbar break for new row
    main_window.addToolBarBreak()
    
    # Format toolbar (new row)
    format_toolbar = main_window.addToolBar("Format")
    format_toolbar.addAction("Bold")
    format_toolbar.addAction("Italic")
    format_toolbar.addAction("Underline")
    
    # Status toolbar at bottom
    status_toolbar = main_window.addToolBar("Status", Qt.BottomToolBarArea)
    status_toolbar.addAction("Status: Ready")
    
    # 5. Demonstrate dynamic toolbar insertion
    # Insert priority toolbar before edit toolbar
    priority_toolbar = main_window.insertToolBar(edit_toolbar, "Priority")
    priority_toolbar.addAction("Important Action")
    
    # Add break before priority toolbar to reorganize layout
    main_window.insertToolBarBreak(priority_toolbar)
    
    main_window.show()

    # Toolbar state is automatically saved/restored with layout
    sys.exit(app.exec())
```

This example demonstrates:
- **Multi-area toolbar support**: Top and bottom toolbar areas
- **Toolbar breaks**: Creating rows/columns within areas  
- **Dynamic insertion**: Adding toolbars between existing ones
- **Automatic persistence**: Toolbar layouts saved with application state

## Complete Examples and Testing

### Comprehensive Test Suite

JCDock includes a modular test suite that demonstrates all framework capabilities and serves as both a testing framework and reference implementation. To run the test suite:

```bash
# From project root directory
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
- `application_closing(layout_data)` - Application closing with current layout data

***
## API Reference

### Public API (Recommended)
The streamlined public API focuses on the universal `create_window()` method:

```python
from JCDock import DockingManager, persistable

manager = DockingManager()
window = manager.create_window(content=widget, title="Title", persist=True)
```

**Available Public Imports:**
- `DockingManager` - Central API for all operations
- `persistable` - Decorator for widgets with layout persistence
- `get_registry()` - Access to the global widget registry

### Internal Components
These components are documented for reference but should not be accessed directly:
- `WidgetFactory` - Internal widget creation (use `DockingManager.create_window()`)
- `DockContainer` - Internal container implementation (created by `create_window()`)
- `DockPanel` - Internal widget wrapper (created automatically)
- Various utility classes (caching, performance monitoring, etc.)

### Migration from Older APIs
If you're using older JCDock versions, replace deprecated methods:
- `create_simple_floating_widget()` → `create_window()`
- `create_floating_widget_from_key()` → `create_window()` with registry
- `@dockable` → `@persistable`

***
## Additional Documentation

- **[wiki/](wiki/)** - Comprehensive API documentation and usage guides
- **CLAUDE.md** - Development guidelines and context for development tools

## License

This project is licensed under the MIT License - see the LICENSE file for details.