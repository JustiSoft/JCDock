# JCDock Simple Examples

This directory contains simple, focused examples demonstrating individual JCDock features. Each script is designed to be minimal, easy to understand, and demonstrates the correct JCDock architecture patterns.

## Key Architecture Understanding

JCDock follows a **widget-centric architecture** where:
- **Widgets ARE containers** - Every content widget gets wrapped in a DockPanel and lives inside a DockContainer
- **Floating first** - Widgets are created as floating containers, then docked together
- **Widget-to-widget docking** - Widgets dock to each other, not to empty "dock areas"

## Universal Widget Creation

JCDock uses a single universal `create_window()` method for all widget creation scenarios:

### Simple Floating Widgets
```python
# Create any widget as a floating window
window = manager.create_window(
    content=content_widget,   # Any QWidget
    title="Widget Title",
    x=100, y=100, width=300, height=200
)
```

### Persistent Widgets (With Layout Restoration)
```python
# Use @persistable decorator for widgets that restore from saved layouts
@persistable("widget_key", "Widget Title")
class MyWidget(QWidget):
    def get_dock_state(self):
        return {"data": "widget state"}
    
    def set_dock_state(self, state):
        # Restore widget state
        pass

window = manager.create_window(
    content=MyWidget(),
    key="widget_key",  # Must match @persistable key
    title="Widget Title",
    persist=True  # Include in layout persistence
)
```

## Examples

### 1. `basic_containers.py`
**Purpose**: Demonstrates the most basic JCDock setup
- Creating floating widgets using `create_window()`
- Basic drag-and-drop docking between widgets
- Simple widget creation without persistence

**What you'll see**: Two floating widgets that can be docked together by dragging tabs.

**Key Learning**: Understanding the fundamental widget-to-widget docking pattern with the universal API.

### 2. `main_window_with_menu.py`
**Purpose**: Shows proper main application window setup
- Main window created with `create_window(is_main_window=True)`
- Floating widgets created with `create_window()`
- Programmatic docking using `dock_widget(source, target, position)`
- Menu bar integration

**What you'll see**: A main application window with menu. Create widgets and dock them programmatically.

**Key Learning**: Using the universal `create_window()` API for both main windows and content widgets.

### 3. `icon_demo.py`
**Purpose**: Comprehensive icon demonstration
- Floating widgets created with `create_window()`
- Setting icons using widget icon properties
- Qt standard icons and dynamic icon changes
- Icon persistence through docking operations

**What you'll see**: Multiple widgets with different icon types, icon animation, and persistence through docking.

**Key Learning**: How icons work throughout the docking system and persist through operations.

### 4. `save_load_demo.py` (Comprehensive)
**Purpose**: Complete application workflow with persistence
- Widget registration using `@persistable` decorator
- Persistent widget creation with `create_window(persist=True)`
- Layout and state persistence with save/load
- Complex widget state handlers

**What you'll see**: A complete application with note and counter widgets. Widget content and layout persist across save/load cycles.

**Key Learning**: Full application development pattern with the unified persistence system.

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

# Create floating window using universal API
window = manager.create_window(
    content=content,
    title="My Widget", 
    x=100, y=100, width=300, height=200
)

# Window includes icon support and automatic management
window.show()
```

### Programmatic Docking
```python
# Create two widgets
widget1_window = manager.create_window(content=QLabel("Widget 1"), title="Widget 1")
widget2_window = manager.create_window(content=QLabel("Widget 2"), title="Widget 2")

# Dock widget1 to widget2 at center (creates tab group)
manager.dock_widget(widget1_window, widget2_window, "center")

# Dock to sides (creates split layout)
manager.dock_widget(widget1_window, widget2_window, "left")   # or "right", "top", "bottom"
```

### Main Window Setup
```python
# Create main application window using universal API
main_window = manager.create_window(
    title="My Application",
    is_main_window=True,  # Exits app when closed
    persist=True,         # Include in layout persistence
    width=1000,
    height=600
)

# Window automatically registered and ready for docking
```

### Widget Registration (for persistence)
```python
@persistable("my_widget", "My Widget Title")
class MyWidget(QWidget):
    def get_dock_state(self):
        return {"data": "my_state"}
    
    def set_dock_state(self, state):
        # Restore state from saved layout
        pass

# Create persistent widget window
window = manager.create_window(
    content=MyWidget(),
    key="my_widget",     # Must match @persistable key
    title="My Widget",
    persist=True         # Enable layout persistence
)
```

## Architecture Insights

### What NOT to Do (Common Mistakes)
```python
# DON'T create DockContainer directly for content widgets
container = DockContainer(manager=manager)  # Use create_window() instead

# DON'T use deprecated method names
widget = manager.create_simple_floating_widget()  # Method doesn't exist in public API

# DON'T try to manually add widgets to containers
container.addWidget(widget)  # Use create_window() instead
```

### The Correct JCDock Way
```python
# DO use the universal create_window() method
window = manager.create_window(content=widget, title="My Widget")

# DO dock widgets to each other
manager.dock_widget(widget1, widget2, "center")

# DO use @persistable for persistent widgets
@persistable("my_widget", "My Widget")
class MyWidget(QWidget): pass

window = manager.create_window(
    content=MyWidget(), 
    key="my_widget", 
    persist=True
)
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
- **Use simple widgets for prototyping**: `create_window()` is perfect for testing
- **Use registered widgets for production**: `@persistable` decorator provides persistence
- **Let users control layout**: Enable drag-and-drop by default
- **Test with multiple monitors**: JCDock handles multi-monitor scenarios well
- **Icons enhance UX**: Users rely on icons to identify widgets in complex layouts