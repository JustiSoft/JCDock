# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

JCDock is a flexible and customizable docking framework for PySide6 applications. It enables creating complex UIs where widgets can be docked, undocked, and rearranged dynamically.

## Current Project Objectives

### Guiding Rules for Development
- **One Step at a Time**: Adhere strictly to the plan. Do not combine steps.
- **Test After Every Step**: After completing the changes for each chunk, stop and perform the required tests. Do not proceed until all tests for the current step pass.
- **No New Features**: The goal is to refactor the existing implementation to be more robust. The final functionality should be identical to the user; only the underlying architecture changes.

## Core Architecture

### Central Components

- **DockingManager** (`src/JCDock/docking_manager.py`): Central orchestrator that manages all docking operations, widget registration, layout persistence, and emits signals for layout changes. Now includes a robust state machine for tracking operational states
- **DockingState** (`src/JCDock/docking_state.py`): Enum defining the 5 operational states (IDLE, RENDERING, DRAGGING_WINDOW, RESIZING_WINDOW, DRAGGING_TAB)
- **DockPanel** (`src/JCDock/dock_panel.py`): Wrapper for any QWidget to make it dockable with title bars and controls
- **DockContainer** (`src/JCDock/dock_container.py`): Advanced host containers with drag-and-drop capabilities, visual overlays, and sophisticated tab/splitter management
- **TearableTabWidget** (`src/JCDock/tearable_tab_widget.py`): Enhanced tab widget supporting tear-out operations with visual feedback
- **MainDockWindow** (`src/JCDock/main_dock_window.py`): Main application window that hosts the central dock area
- **FloatingDockRoot** (`src/JCDock/floating_dock_root.py`): Independent floating windows that can act as docking targets
- **HitTestCache** (`src/JCDock/hit_test_cache.py`): Performance optimization for overlay hit-testing during drag operations
- **IconCache** (`src/JCDock/icon_cache.py`): LRU cache system for icon rendering performance optimization

### Key Patterns

- All widgets must be wrapped in `DockPanel` and registered with the `DockingManager`
- Containers are registered as dock areas using `manager.register_dock_area()`
- The main window's central widget should be a `DockContainer` with `show_title_bar=False`
- Layout persistence uses the `LayoutModel` system with serializable node structures
- Tearable tabs provide drag-and-drop functionality with real-time visual feedback via overlay system
- Performance is optimized through caching systems for icons and hit-test operations
- Visual overlays show valid drop zones during drag operations for enhanced user experience
- State machine ensures predictable operation flow and prevents phantom overlay/event issues
- Hit test cache only considers visible tabs as drop targets to prevent overlay confusion

### Signal System

DockingManager emits signals via `manager.signals`:
- `widget_docked(widget, container)` - when widget is docked
- `widget_undocked(widget)` - when widget becomes floating
- `widget_closed(persistent_id)` - before widget is closed
- `layout_changed()` - after any layout modification


The project uses standard Python tooling with pyproject.toml configuration

### Code formatting requirements

**STRICT RULE: Do not add new comments to the code.**

The ONLY exception is when creating a new function or class - then add a brief docstring with a high level description.

**What NOT to add:**
- Inline comments explaining what code does
- Comments above code blocks
- TODO comments
- Implementation detail comments
- Comments explaining why something was changed

**What IS allowed:**
- Docstrings for new functions/classes only
- Existing comments should be preserved as-is

### Testing

Only run tests when there is a specific need to test new features or verify functionality.

**Virtual Environment Activation:**
Use the Python executable directly from the virtual environment:
```
.venv/Scripts/python.exe <script_path>
```

**Do NOT use these methods (they don't work in this environment):**
- `call .venv\Scripts\activate.bat && python <script>`
- `.venv\\Scripts\\activate.bat && python <script>`
- `source .venv/Scripts/activate`

**Testing Script:**
Use src/JCDock/Examples/dock_test.py as a testing script to confirm any changes made are correct and error free

### Visual Diff Tools

**Meld (Preferred):**
When user requests to see code differences in a visual diff tool:
1. Create temporary files: `git show <commit1>:<file> > file_before.py && git show <commit2>:<file> > file_after.py`
2. Launch Meld: `"C:\Program Files\Meld\Meld.exe" file_before.py file_after.py`
3. Clean up: `rm file_before.py file_after.py`

**Alternative Methods:**
- WinMerge (if available): `"C:\Program Files\WinMerge\WinMergeU.exe" file_before.py file_after.py`
- Git built-in: `git diff --no-index --color=always file_before.py file_after.py`

## Security and Collaboration Guidelines
- Never commit anything to GitHub without permission

### CRITICAL COMMIT MESSAGE RULE
**🚨 NEVER add "Co-Authored-By: Claude" or "Generated with Claude Code" messages to git commits 🚨**

This is a STRICT requirement that must NEVER be violated. Git commits should contain only:
- A clear, descriptive commit message explaining the changes
- NO attribution to Claude or Claude Code
- NO generated signatures or footers

## Code Discovery Guidelines

### Quick Context-Finding Strategies

**For Widget Lifecycle Issues:**
- Start with `DockingManager` (`docking_manager.py`) - central orchestrator for all operations
- Check `register_widget()`, `register_dock_area()`, and `unregister_widget()` methods
- Look for `_rendering_layout`, `_undocking_in_progress`, and `_is_user_dragging` flags

**For Visual/UI Issues:**
- `DockContainer` (`dock_container.py`) - handles visual overlays, shadows, and layout
- `TitleBar` (`title_bar.py`) - title bar rendering and controls
- `DockingOverlay` (`docking_overlay.py`) - drag-and-drop visual feedback

**For Drag-and-Drop Problems:**
- `TearableTabWidget` (`tearable_tab_widget.py`) - tab tear-out mechanics
- `DockingManager.handle_drag_*` methods for drag event processing
- `HitTestCache` (`hit_test_cache.py`) - performance optimization for overlay hit-testing

**For Layout/Persistence Issues:**
- `LayoutModel` and related classes in `dock_model.py`
- `DockingManager.model` property and related methods
- Look for `roots` dictionary and node structures (SplitterNode, TabGroupNode, WidgetNode)

### Common Search Patterns

- **Signal connections**: Search for `.connect(` to find event bindings
- **Widget registration**: Search for `register_` to find registration points
- **State flags**: Search for `_is_`, `_rendering_`, `_undocking_` for state management
- **Event handlers**: Search for `Event` or `event` to find Qt event processing
- **Factory patterns**: Search for `create_` methods for object creation
- **Cache operations**: Search for `cache` or `_cache` for performance optimizations

## Component Interaction Reference

### Core Component Dependencies

**DockingManager** (Central Hub):
- Manages all widgets and containers via `widgets[]` and `containers[]` lists
- Coordinates with `LayoutModel` for persistence
- Uses `HitTestCache` for performance optimization
- Emits signals via `DockingSignals` class

**DockPanel** (Widget Wrapper):
- Always registered with `DockingManager` via `register_widget()`
- Contains a `TitleBar` and content widget
- Tracks `parent_container` reference
- Uses `persistent_id` for layout persistence

**DockContainer** (Host Container):
- Registered as dock area via `register_dock_area()`
- Contains `TearableTabWidget` for tabbed interface
- Uses `DockingOverlay` for drag-and-drop feedback
- Can be persistent root (`_is_persistent_root` flag)

**TearableTabWidget** (Tab Management):
- Handles tab tear-out operations with drag feedback
- Creates new `DockContainer` instances for detached tabs
- Communicates with `DockingManager` for drag events

### Common Interaction Patterns

1. **Widget Registration Flow**: Widget → DockPanel → DockingManager.register_widget() → Assignment to DockContainer
2. **Drag Operations**: TearableTabWidget → DockingManager.handle_drag_* → HitTestCache → DockingOverlay
3. **Layout Changes**: Any change → DockingManager.model update → signals.layout_changed emission

## Debugging Context Maps

### Widget Disappearing Issues
**Check these locations in order:**
1. `DockingManager.state` - check current state via `is_rendering()` or debug output
2. `DockingManager.eventFilter()` - master guard prevents events during non-idle states
3. `DockContainer._is_persistent_root` - persistent roots should never be closed
4. `DockingManager.unregister_widget()` - widget removal logic
5. `LayoutModel.remove_widget()` - model cleanup

### Mouse Control/Drag Issues
**Check these locations:**
1. `DockingManager.state` - check if stuck in `DRAGGING_WINDOW`, `RESIZING_WINDOW`, or `DRAGGING_TAB`
2. `DockingManager.is_user_interacting()` - prevents window stacking during operations
3. `TearableTabWidget.mousePressEvent/mouseMoveEvent` - tab drag initiation
4. `DockingManager.handle_drag_*` methods - drag event processing
5. `HitTestCache` - overlay hit-testing performance (check for invisible tab caching)
6. `DockingOverlay.update_overlay_position()` - visual feedback positioning

### State Machine Debugging
**Enable debug mode to see state transitions:**
```python
manager.set_debug_mode(True)  # Shows "STATE: idle -> rendering" etc.
```
**Check these for state issues:**
1. State stuck in non-IDLE - look for missing `finally` blocks in state transition code
2. Multiple overlays - check `HitTestCache._cache_traversal_targets()` for invisible tab caching
3. Event blocking - verify `eventFilter()` logic and state checks

### Focus/Activation Issues
**Check these locations:**
1. `DockingManager._is_updating_focus` - serializes focus changes (kept separate from state machine)
2. `DockingManager.set_active_widget()` - widget activation logic
3. `DockContainer.focus*` methods - container focus handling
4. Qt window activation events in containers

### Layout/Persistence Issues
**Check these locations:**
1. `LayoutModel.roots` dictionary - root container tracking
2. `DockingManager._is_persistent_root()` - persistent root identification
3. `LayoutModel.serialize_layout()/restore_layout()` - persistence logic
4. Node structures: `SplitterNode`, `TabGroupNode`, `WidgetNode`

## Code Organization Principles

### Naming Conventions
- **Private methods**: Start with `_` (e.g., `_update_container_root()`)
- **State flags**: Use `_is_` or `_rendering_` prefixes (e.g., `_is_user_dragging`)
- **Signal handlers**: Use `handle_` or `on_` prefixes
- **Factory methods**: Use `create_` prefix
- **Cache methods**: Include `cache` in name

### Class Structure Patterns
- **Manager classes**: Central coordination, maintain lists/dictionaries of managed objects
- **Widget classes**: Inherit from QWidget, have `manager` reference, use composition over inheritance
- **Model classes**: Data structures for persistence, use node-based hierarchies
- **Utility classes**: Static methods, caching, performance optimization

### Method Organization
- **Public API**: Widget registration, layout operations, user-facing methods
- **Private helpers**: `_method_name()` for internal coordination
- **Event handlers**: Qt event system overrides (`mousePressEvent`, etc.)
- **Signal handlers**: Methods connected to Qt signals

### File Responsibilities
- **`docking_manager.py`**: Central coordination, widget/container management
- **`dock_container.py`**: Visual container, drag-and-drop target, layout hosting
- **`dock_panel.py`**: Widget wrapper, title bar management
- **`tearable_tab_widget.py`**: Tab management, drag operations
- **`dock_model.py`**: Data structures, serialization/persistence
- **Utility files**: Performance optimization (`hit_test_cache.py`, `icon_cache.py`)

## State Management Reference

### Widget State Tracking
- **Registration**: `DockingManager.widgets[]` list contains all registered DockPanels
- **Parent Tracking**: `DockPanel.parent_container` references hosting DockContainer
- **Persistence**: `DockPanel.persistent_id` for layout restoration

### Container State Management
- **Container Registry**: `DockingManager.containers[]` list of all DockContainers
- **Root Tracking**: `LayoutModel.roots{}` dictionary maps containers to root nodes
- **Persistent Roots**: `DockContainer._is_persistent_root` flag prevents closure

### Layout Model Flow
1. **Live State**: Current widget/container relationships in memory
2. **Model Serialization**: `LayoutModel.serialize_layout()` creates persistent representation
3. **Model Restoration**: `LayoutModel.restore_layout()` rebuilds UI from serialized data
4. **Node Hierarchy**: SplitterNode → TabGroupNode → WidgetNode structure

### State Machine Management
- **`DockingManager.state`**: Current operational state (DockingState enum)
- **`_set_state()`**: Central method for all state transitions with debug output
- **`is_idle()`**: Check if manager is in IDLE state
- **`is_rendering()`**: Check if layout is being rendered
- **`is_user_interacting()`**: Check if user is dragging/resizing windows or tabs
- **`_is_updating_focus`**: Serializes focus-change painting to prevent GDI conflicts (separate from state machine)

### Signal Flow
1. **Action occurs** (widget dock/undock/close)
2. **State updated** in DockingManager and LayoutModel
3. **Signal emitted** via `DockingSignals` (widget_docked, widget_undocked, etc.)
4. **Listeners respond** to update UI, persist state, etc.

## Development Environment

### CLI Tools
- **Github CLI is located at `C:\Program Files\GitHub CLI\gh.exe`**

### Branch Protection Management for Repository Owner

**Option 1: Direct Push (Simplest for Admin)**
As repository owner, you can push directly to master without PRs:

```bash
# 1. Temporarily disable protection
"C:\Program Files\GitHub CLI\gh.exe" api repos/JustiSoft/JCDock/branches/master/protection --method DELETE

# 2. Make your changes and commit normally
git add . && git commit -m "Your changes"

# 3. Push directly to master
git push origin master

# 4. Restore protection
"C:\Program Files\GitHub CLI\gh.exe" api repos/JustiSoft/JCDock/branches/master/protection --method PUT --input minimal_protection.json
```

**Option 2: PR Workflow (When you want code review process)**
When you need to merge your own PR as the repository owner (since GitHub prevents PR authors from approving their own PRs):

**Step 1: Save current protection settings**
```bash
"C:\Program Files\GitHub CLI\gh.exe" api repos/JustiSoft/JCDock/branches/master/protection --method GET > protection_backup.json
```

**Step 2: Temporarily disable branch protection**
```bash
"C:\Program Files\GitHub CLI\gh.exe" api repos/JustiSoft/JCDock/branches/master/protection --method DELETE
```

**Step 3: Merge the PR**
```bash
"C:\Program Files\GitHub CLI\gh.exe" pr merge [PR_NUMBER] --squash --delete-branch
```

**Step 4: Restore minimal branch protection**
Create `minimal_protection.json`:
```json
{
  "required_status_checks": null,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1
  },
  "enforce_admins": true,
  "restrictions": null
}
```

Then restore protection:
```bash
"C:\Program Files\GitHub CLI\gh.exe" api repos/JustiSoft/JCDock/branches/master/protection --method PUT --input minimal_protection.json
```

This workflow allows you to bypass the "authors can't approve their own PRs" restriction while maintaining branch protection for regular operations.