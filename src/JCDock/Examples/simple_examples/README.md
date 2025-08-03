# JCDock Simple Examples

This directory contains simple, focused examples demonstrating individual JCDock features. Each script is designed to be minimal, easy to understand, and demonstrates the correct JCDock architecture patterns.

## Key Architecture Understanding

JCDock follows a **widget-centric architecture** where:
- **Widgets ARE containers** - Every content widget gets wrapped in a DockPanel and lives inside a DockContainer
- **Floating first** - Widgets are created as floating containers, then docked together
- **Widget-to-widget docking** - Widgets dock to each other, not to empty "dock areas"

## Widget Creation Patterns

JCDock provides two main widget creation methods:

### 1. Simple Widgets (No Persistence)
```python
# For basic examples - simple but not persistent
container, panel = manager.create_simple_floating_widget(
    content_widget,           # Any QWidget
    title="Widget Title",
    x=100, y=100, width=300, height=200
)
```

### 2. Registered Widgets (Persistent)
```python
# For applications with save/load - persistent across sessions
@dockable("widget_key", "Widget Title")
class MyWidget(QWidget):
    pass

container = manager.create_floating_widget_from_key("widget_key")
```

## Examples

### 1. `basic_containers.py`
**Purpose**: Demonstrates the most basic JCDock setup
- Creating floating widgets using `create_simple_floating_widget()`
- Basic drag-and-drop docking between widgets
- No registration system needed

**What you'll see**: Two floating widgets that can be docked together by dragging tabs.

**Key Learning**: Understanding the fundamental widget-to-widget docking pattern.

### 2. `main_window_with_menu.py`
**Purpose**: Shows proper main application window setup
- DockContainer as main window (correct use of manual container creation)
- Simple floating widgets created with `create_simple_floating_widget()`
- Programmatic docking using `dock_widget(source, target, position)`
- Menu bar integration

**What you'll see**: A main application window with menu. Create widgets and dock them programmatically.

**Key Learning**: When to use DockContainer directly (main windows) vs. widget creation methods (content).

### 3. `icon_demo.py`
**Purpose**: Comprehensive icon demonstration
- Simple floating widgets with `create_simple_floating_widget()`
- Setting icons using `panel.set_icon()`
- Qt standard icons and dynamic icon changes
- Icon persistence through docking operations

**What you'll see**: Multiple widgets with different icon types, icon animation, and persistence through docking.

**Key Learning**: How icons work throughout the docking system and persist through operations.

### 4. `save_load_demo.py` (Comprehensive)
**Purpose**: Complete application workflow with persistence
- Widget registration using `@dockable` decorator
- Persistent widget creation with `create_floating_widget_from_key()`
- Layout and state persistence with save/load
- Complex widget state handlers

**What you'll see**: A complete application with note and counter widgets. Widget content and layout persist across save/load cycles.

**Key Learning**: Full application development pattern with persistence.

## Learning Progression

1. **Start with `basic_containers.py`** - Learn fundamental docking concepts
2. **Move to `main_window_with_menu.py`** - Understand main window patterns and programmatic docking
3. **Try `icon_demo.py`** - Explore visual customization and dynamic updates
4. **Master `save_load_demo.py`** - Complete application development with persistence

## Running the Examples

### Prerequisites
- Python 3.8+
- PySide6
- JCDock library (local development version)

### How to Run
From this directory (`simple_examples/`), run any example:

```bash
python basic_containers.py
python main_window_with_menu.py
python icon_demo.py
python save_load_demo.py
```

**Note**: These examples use the local development version of JCDock rather than any installed version.

## Common Patterns Demonstrated

### Creating Simple Floating Widgets
```python
# Simple content widget
content = QLabel("Hello World")

# Create floating container
container, panel = manager.create_simple_floating_widget(
    content, "My Widget", x=100, y=100, width=300, height=200
)

# Set icon on the panel
panel.set_icon(app.style().standardIcon(app.style().StandardPixmap.SP_ComputerIcon))

# Show the container
container.show()
```

### Programmatic Docking
```python
# Dock widget1 to widget2 at center (creates tab group)
manager.dock_widget(panel1, panel2, "center")

# Dock to sides (creates split layout)
manager.dock_widget(panel1, panel2, "left")   # or "right", "top", "bottom"
```

### Main Window Setup
```python
main_window = DockContainer(
    manager=manager,
    show_title_bar=True,
    is_main_window=True,
    window_title="My App",
    auto_persistent_root=True
)
manager.register_dock_area(main_window)
manager.set_main_window(main_window)
```

### Widget Registration (for persistence)
```python
@dockable("my_widget", "My Widget Title")
class MyWidget(QWidget):
    def get_dock_state(self):
        return {"data": "my_state"}
    
    def set_dock_state(self, state):
        # Restore state
        pass

# Create registered widget
container = manager.create_floating_widget_from_key("my_widget")
```

## Architecture Insights

### What NOT to Do (Common Mistakes)
```python
# DON'T create empty containers manually for content
container = DockContainer(manager=manager)  # Wrong for content widgets

# DON'T use internal methods
widget = manager._create_panel_from_key()  # Internal method

# DON'T try to "dock into" containers
container.addWidget(widget)  # Not how JCDock works
```

### The Correct JCDock Way
```python
# DO create floating widgets first
container, panel = manager.create_simple_floating_widget(content, "Title")

# DO dock widgets to each other
manager.dock_widget(panel1, panel2, "center")

# DO use registration for persistent widgets
@dockable("key", "Title")
class MyWidget(QWidget): pass
container = manager.create_floating_widget_from_key("key")
```

## Key Benefits of This Architecture

1. **Flexibility**: All widgets can be floating or docked
2. **Persistence**: Registered widgets restore their state and position
3. **User Control**: Users can rearrange layouts by dragging tabs
4. **Consistency**: Same widget works in floating and docked states
5. **Simplicity**: No complex container hierarchies to manage

## What's Next?

After mastering these examples:
- Explore the comprehensive test suite in `../test_suite/`
- Read the main JCDock documentation  
- Build your own docking application using these patterns
- Consider advanced features like custom state handlers and complex layouts

## Tips for Development

- **Always start floating**: Create widgets as floating first, then dock them
- **Use simple widgets for prototyping**: `create_simple_floating_widget()` is perfect for testing
- **Use registered widgets for production**: `@dockable` decorator provides persistence
- **Let users control layout**: Enable drag-and-drop by default
- **Test with multiple monitors**: JCDock handles multi-monitor scenarios well
- **Icons enhance UX**: Users rely on icons to identify widgets in complex layouts