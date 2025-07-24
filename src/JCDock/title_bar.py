# title_bar.py

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout, QStyle, QApplication, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QPoint, QRect, QEvent, QRectF
from PySide6.QtGui import QColor, QPainter, QBrush, QMouseEvent, QPainterPath, QPalette, QRegion, QPen, QIcon, QPixmap

from .docking_state import DockingState
from .icon_cache import IconCache


class TitleBar(QWidget):
    def __init__(self, title, parent=None, top_level_widget=None):
        super().__init__(parent)
        self._top_level_widget = top_level_widget if top_level_widget is not None else parent
        self.setObjectName(f"TitleBar_{title.replace(' ', '_')}")
        self.setAutoFillBackground(False)
        self.setFixedHeight(35)
        self.setMouseTracking(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("background: transparent; color: #101010;")
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        layout.addWidget(self.title_label, 1)

        button_style = """
            QPushButton { background-color: transparent; border: none; }
            QPushButton:hover { background-color: #D0D0D0; border-radius: 4px; }
            QPushButton:pressed { background-color: #B8B8B8; }
        """

        self.minimize_button = QPushButton()
        self.minimize_button.setIcon(self._create_control_icon("minimize"))
        self.minimize_button.setFixedSize(24, 24)
        self.minimize_button.setStyleSheet(button_style)
        self.minimize_button.clicked.connect(self._top_level_widget.showMinimized)
        layout.addWidget(self.minimize_button)

        self.maximize_button = QPushButton()
        self.maximize_button.setIcon(self._create_control_icon("maximize"))
        self.maximize_button.setFixedSize(24, 24)
        self.maximize_button.setStyleSheet(button_style)
        if hasattr(self._top_level_widget, 'toggle_maximize'):
            self.maximize_button.clicked.connect(self._top_level_widget.toggle_maximize)
        layout.addWidget(self.maximize_button)

        self.close_button = QPushButton()
        self.close_button.setIcon(self._create_control_icon("close"))
        self.close_button.setFixedSize(24, 24)
        self.close_button.setStyleSheet(button_style)

        # This is the fix: The button now calls the correct manager method based on the window type.
        self.close_button.clicked.connect(self.on_close_button_clicked)

        layout.addWidget(self.close_button)

        self.moving = False
        self.offset = QPoint()

    def paintEvent(self, event):
        """Paint the title bar background with rounded top corners to match container."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get the background color from the parent container
        bg_color = QColor("#F0F0F0")  # Default fallback
        if hasattr(self._top_level_widget, '_title_bar_color'):
            bg_color = self._top_level_widget._title_bar_color
        
        # Create a rounded rectangle path with rounded top corners only
        rect = QRectF(self.rect())
        path = QPainterPath()
        radius = 8.0  # Match container's border-radius
        
        # Start from bottom-left corner (no rounding)
        path.moveTo(rect.left(), rect.bottom())
        # Line to top-left, then arc for top-left rounded corner
        path.lineTo(rect.left(), rect.top() + radius)
        path.arcTo(rect.left(), rect.top(), radius * 2, radius * 2, 180, -90)
        # Line across top to top-right rounded corner
        path.lineTo(rect.right() - radius, rect.top())
        path.arcTo(rect.right() - radius * 2, rect.top(), radius * 2, radius * 2, 90, -90)
        # Line down to bottom-right (no rounding)
        path.lineTo(rect.right(), rect.bottom())
        # Close the path
        path.closeSubpath()
        
        # Fill the path with the background color
        painter.fillPath(path, QBrush(bg_color))
        super().paintEvent(event)

    def on_close_button_clicked(self):
        """
        Determines whether to close a single widget or a whole container.
        """
        # Local import to avoid circular dependency at module level
        from .dock_container import DockContainer

        manager = getattr(self._top_level_widget, 'manager', None)
        if not manager:
            self._top_level_widget.close()
            return

        if isinstance(self._top_level_widget, DockContainer):
            manager.request_close_container(self._top_level_widget)
        else:  # It's a DockPanel
            manager.request_close_widget(self._top_level_widget)

    def mouseMoveEvent(self, event):
        # If the title bar is in "moving" mode, it has two jobs:
        # 1. Move the window directly (live move).
        # 2. Ask the docking manager to check for docking opportunities.
        if self.moving:
            # 1. First notify the manager to create overlays before moving the window.
            if hasattr(self._top_level_widget, 'manager') and self._top_level_widget.manager:
                self._top_level_widget.manager.handle_live_move(self._top_level_widget, event)

            # 2. Then move the window based on the mouse drag (live move).
            new_widget_global = event.globalPosition().toPoint() - self.offset
            self._top_level_widget.move(new_widget_global)

            # The event is fully handled, so we prevent further processing.
            return

        # If not moving, pass the event to the default handler to process
        # other things like hover events for tooltips, etc.
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        # Do not start a drag if clicking on any of the control buttons.
        if (self.close_button.geometry().contains(event.pos()) or
                self.maximize_button.geometry().contains(event.pos()) or
                self.minimize_button.geometry().contains(event.pos())):
            super().mousePressEvent(event)
            return

        if event.button() == Qt.LeftButton:
            # Only DockContainer windows support resizing, not DockPanel content wrappers
            from .dock_container import DockContainer
            
            edge = None
            if isinstance(self._top_level_widget, DockContainer):
                pos = event.pos()
                margin = getattr(self._top_level_widget, 'resize_margin', 8)
                on_left = 0 <= pos.x() < margin
                on_right = self.width() - margin < pos.x() <= self.width()
                on_top = 0 <= pos.y() < margin

                if on_top:
                    if on_left:
                        edge = "top_left"
                    elif on_right:
                        edge = "top_right"
                    else:
                        edge = "top"
                elif on_left:
                    edge = "left"
                elif on_right:
                    edge = "right"

                if edge:
                    self._top_level_widget.resizing = True
                    self._top_level_widget.resize_edge = edge
                    self._top_level_widget.resize_start_pos = event.globalPosition().toPoint()
                    self._top_level_widget.resize_start_geom = self._top_level_widget.geometry()
                    
                    # Set resizing state to prevent window stacking conflicts during resize
                    if hasattr(self._top_level_widget, 'manager') and self._top_level_widget.manager:
                        self._top_level_widget.manager._set_state(DockingState.RESIZING_WINDOW)

            if not edge:
                # A click on the title bar is an activation request for its parent window.
                if hasattr(self._top_level_widget, 'on_activation_request'):
                    self._top_level_widget.on_activation_request()

                # Clean up any existing overlays before starting drag operation
                if hasattr(self._top_level_widget, 'manager') and self._top_level_widget.manager:
                    if hasattr(self._top_level_widget.manager, 'destroy_all_overlays'):
                        self._top_level_widget.manager.destroy_all_overlays()

                self.moving = True
                self.offset = event.globalPosition().toPoint() - self._top_level_widget.pos()
                
                # Build hit test cache and set drag operation state
                if hasattr(self._top_level_widget, 'manager') and self._top_level_widget.manager:
                    manager = self._top_level_widget.manager
                    manager.hit_test_cache.build_cache(manager.window_stack, manager.containers)
                    # Set dragging state to prevent window stacking conflicts during move
                    manager._set_state(DockingState.DRAGGING_WINDOW)
                    manager.hit_test_cache.set_drag_operation_state(True)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            # If we were moving, finalize the operation (move or dock).
            if self.moving:
                # First, clear the moving flag
                self.moving = False
                
                # Check if we have a manager and if there's a dock target
                manager = getattr(self._top_level_widget, 'manager', None)
                if manager and hasattr(manager, 'last_dock_target') and manager.last_dock_target:
                    # A dock target exists - the drag ended over a valid drop zone
                    # Call the manager to finalize the dock operation
                    manager.finalize_dock_from_live_move(self._top_level_widget, manager.last_dock_target)
                
                # Finally, clear the manager's last_dock_target and clean up overlays
                if manager:
                    if hasattr(manager, 'last_dock_target'):
                        manager.last_dock_target = None
                    # Clean up any remaining overlays after the operation
                    if hasattr(manager, 'destroy_all_overlays'):
                        manager.destroy_all_overlays()
                    # Reset drag operation state
                    if hasattr(manager, 'hit_test_cache'):
                        manager.hit_test_cache.set_drag_operation_state(False)
                    # Return to idle state to allow window stacking again
                    manager._set_state(DockingState.IDLE)

            # Reset resizing flags on the parent (only for DockContainer windows).
            if hasattr(self._top_level_widget, 'resizing') and self._top_level_widget.resizing:
                self._top_level_widget.resizing = False
                self._top_level_widget.resize_edge = None
                
                # Return to idle state after resize operation
                if hasattr(self._top_level_widget, 'manager') and self._top_level_widget.manager:
                    self._top_level_widget.manager._set_state(DockingState.IDLE)

    def _create_control_icon(self, icon_type: str, color=QColor("#303030")):
        """
        Creates cached window control icons for improved performance.
        """
        return IconCache.get_control_icon(icon_type, color.name(), 24)