# dockable_widget.py

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout, QStyle, QApplication
from PySide6.QtCore import Qt, QPoint, QRect, QEvent, QRectF
from PySide6.QtGui import QColor, QPainter, QBrush, QMouseEvent, QPainterPath, QPalette, QRegion, QPen, QIcon, QPixmap

from .docking_overlay import DockingOverlay


class TitleBar(QWidget):
    def __init__(self, title, parent=None, top_level_widget=None):
        super().__init__(parent)
        self._top_level_widget = top_level_widget if top_level_widget is not None else parent
        self.setObjectName(f"TitleBar_{title.replace(' ', '_')}")
        self.setAutoFillBackground(False)
        self.setFixedHeight(35)
        self.setMouseTracking(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
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
        else:  # It's a DockableWidget
            manager.request_close_widget(self._top_level_widget)

    def mouseMoveEvent(self, event):
        # If the title bar is in "moving" mode, it has two jobs:
        # 1. Move the window.
        # 2. Ask the docking manager to check for docking opportunities.
        if self.moving:
            # 1. Move the window based on the mouse drag.
            new_widget_global = event.globalPosition().toPoint() - self.offset
            self._top_level_widget.move(new_widget_global)

            # 2. Delegate the complex docking logic to the manager.
            if self._top_level_widget.manager:
                self._top_level_widget.manager.handle_drag_move(self._top_level_widget, event)

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
            pos = event.pos()
            margin = self._top_level_widget.resize_margin
            on_left = 0 <= pos.x() < margin
            on_right = self.width() - margin < pos.x() <= self.width()
            on_top = 0 <= pos.y() < margin

            edge = None
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
            else:
                # A click on the title bar is an activation request for its parent window.
                if hasattr(self._top_level_widget, 'on_activation_request'):
                    self._top_level_widget.on_activation_request()

                self.moving = True
                self.offset = event.globalPosition().toPoint() - self._top_level_widget.pos()
                self.grabMouse()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            # If we were moving, stop the move and release the mouse capture.
            if self.moving:
                self.moving = False
                self.releaseMouse()

            # Reset resizing flags on the parent.
            if self._top_level_widget.resizing:
                self._top_level_widget.resizing = False
                self._top_level_widget.resize_edge = None

    def _create_control_icon(self, icon_type: str, color=QColor("#303030")):
        """Draws custom thin icons for window controls."""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(color, 1.2)
        painter.setPen(pen)

        # Center the drawing in a 10x10 area inside the 24x24 pixmap
        rect = QRect(7, 7, 10, 10)

        if icon_type == "minimize":
            painter.drawLine(rect.left(), rect.center().y() + 1, rect.right(), rect.center().y() + 1)
        elif icon_type == "maximize":
            painter.drawRect(rect)
        elif icon_type == "restore":
            # Draw back window
            painter.drawRect(rect.adjusted(0, 2, -2, 0))
            # Draw front window by erasing the intersection and then drawing the new rect
            front_rect = rect.adjusted(2, 0, 0, -2)
            erase_path = QPainterPath()
            erase_path.addRect(QRectF(front_rect))
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillPath(erase_path, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.drawRect(front_rect)
        elif icon_type == "close":
            painter.drawLine(rect.topLeft().x(), rect.topLeft().y(), rect.bottomRight().x(), rect.bottomRight().y())
            painter.drawLine(rect.topRight().x(), rect.topRight().y(), rect.bottomLeft().x(), rect.bottomLeft().y())

        painter.end()
        return QIcon(pixmap)

class DockableWidget(QWidget):
    def __init__(self, title, parent=None, manager=None, persistent_id=None, title_bar_color=None):
        super().__init__(parent)

        self.persistent_id = persistent_id
        self._blur_radius = 25
        self._shadow_color_unfocused = QColor(0, 0, 0, 40)
        self._shadow_color_focused = QColor(0, 0, 0, 75)
        self._feather_power = 3.0
        self._shadow_color = self._shadow_color_focused

        # Set the color based on whether the parameter was provided.
        if title_bar_color is not None:
            self._title_bar_color = title_bar_color
        else:
            self._title_bar_color = QColor("#E0E1E2")  # Default title bar color

        self.setObjectName(f"DockableWidget_{title.replace(' ', '_')}")
        self.setWindowTitle(title)
        self.manager = manager

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)

        self.setFocusPolicy(Qt.StrongFocus)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(self._blur_radius, self._blur_radius, self._blur_radius, self._blur_radius)
        self.main_layout.setSpacing(0)

        self.title_bar = TitleBar(title, self, top_level_widget=self)
        self.main_layout.addWidget(self.title_bar)

        self.content_container = QWidget()
        self.content_container.setObjectName("ContentContainer")
        self.content_container.setMouseTracking(True)
        self.main_layout.addWidget(self.content_container)

        self.content_layout = QVBoxLayout(self.content_container)
        self.content_widget = None
        self.overlay = None
        self.parent_container = None

        self.setMinimumSize(300 + 2 * self._blur_radius, 200 + 2 * self._blur_radius)
        self.resize(300 + 2 * self._blur_radius, 200 + 2 * self._blur_radius)

        self.resize_margin = 8
        self.resizing = False
        self.resize_edge = None
        self.resize_start_pos = None
        self.resize_start_geom = None

        # State for maximize/restore functionality
        self._is_maximized = False
        self._normal_geometry = None

        self.is_tabbed = False
        self.setMouseTracking(True)
        self.installEventFilter(self)

    def set_title_bar_color(self, new_color: QColor):
        """
        Sets the background color of the widget's title bar.
        """
        self._title_bar_color = new_color
        self.update()  # Trigger a repaint to show the new color

    def toggle_maximize(self):
        """Toggles the window between a maximized and normal state."""
        if self._is_maximized:
            # Restore to the previous geometry
            self.main_layout.setContentsMargins(self._blur_radius, self._blur_radius, self._blur_radius,
                                                self._blur_radius)
            self.setGeometry(self._normal_geometry)
            self._is_maximized = False
            # Change icon back to 'maximize'
            self.title_bar.maximize_button.setIcon(self.title_bar._create_control_icon("maximize"))
        else:
            # Maximize the window
            self._normal_geometry = self.geometry()  # Save current geometry
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            screen = QApplication.screenAt(self.pos())
            if not screen:
                screen = QApplication.primaryScreen()
            self.setGeometry(screen.availableGeometry())
            self._is_maximized = True
            # Change icon to 'restore'
            self.title_bar.maximize_button.setIcon(self.title_bar._create_control_icon("restore"))

    def on_activation_request(self):
        """
        Handles a request to activate this widget, bringing it to the front
        of the stacking order.
        """
        self.raise_()
        self.setFocus()
        if self.manager:
            self.manager.bring_to_front(self)

    def mouseReleaseEvent(self, event):
        # This method is now only responsible for stopping a resize operation.
        if self.resizing:
            self.resizing = False
            self.resize_edge = None

        # The 'moving' state is now correctly handled by the TitleBar's release event.
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        # Local import to prevent circular dependency
        from .dock_container import DockContainer

        content_rect = self.rect().adjusted(
            self._blur_radius, self._blur_radius,
            -self._blur_radius, -self._blur_radius
        )
        pos = event.position().toPoint()

        # Handle click-through for shadows.
        if not content_rect.contains(pos):
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            underlying = QApplication.widgetAt(event.globalPosition().toPoint())
            if underlying and underlying.window() is not self:
                target_window = underlying.window()
                if target_window:
                    target_window.raise_()
                    target_window.activateWindow()
                    if self.manager and isinstance(target_window, (DockableWidget, DockContainer)):
                        self.manager.bring_to_front(target_window)
                    QApplication.sendEvent(underlying, event)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            return

        # On any standard press, trigger the activation logic.
        self.on_activation_request()

        # Check for resize edges only if the widget is not docked and not maximized.
        if not self.parent_container and not self._is_maximized:
            self.resize_edge = self.get_edge(pos)
            if self.resize_edge:
                self.resizing = True
                self.resize_start_pos = event.globalPosition().toPoint()
                self.resize_start_geom = self.geometry()
            else:
                # If not resizing, pass the event to children (like the TitleBar).
                super().mousePressEvent(event)
        else:
            # If docked or maximized, never check for resize. Pass the event to children.
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # Only process resize logic if the widget is floating and not maximized.
        if not self.parent_container and not self._is_maximized:
            if self.resizing:
                delta = event.globalPosition().toPoint() - self.resize_start_pos
                new_geom = QRect(self.resize_start_geom)
                if "right" in self.resize_edge: new_geom.setWidth(self.resize_start_geom.width() + delta.x())
                if "left" in self.resize_edge:
                    new_width = self.resize_start_geom.width() - delta.x()
                    if new_width < self.minimumWidth(): new_width = self.minimumWidth()
                    new_geom.setX(self.resize_start_geom.right() - new_width)
                    new_geom.setWidth(new_width)
                if "bottom" in self.resize_edge: new_geom.setHeight(self.resize_start_geom.height() + delta.y())
                if "top" in self.resize_edge:
                    new_height = self.resize_start_geom.height() - delta.y()
                    if new_height < self.minimumHeight(): new_height = self.minimumHeight()
                    new_geom.setY(self.resize_start_geom.bottom() - new_height)
                    new_geom.setHeight(new_height)
                if new_geom.width() < self.minimumWidth(): new_geom.setWidth(self.minimumWidth())
                if new_geom.height() < self.minimumHeight(): new_geom.setHeight(self.minimumHeight())
                self.setGeometry(new_geom)
            else:
                # Set resize cursors if not dragging/resizing.
                edge = self.get_edge(event.position().toPoint())
                if edge:
                    if edge in ["top", "bottom"]:
                        self.setCursor(Qt.SizeVerCursor)
                    elif edge in ["left", "right"]:
                        self.setCursor(Qt.SizeHorCursor)
                    elif edge in ["top_left", "bottom_right"]:
                        self.setCursor(Qt.SizeFDiagCursor)
                    elif edge in ["top_right", "bottom_left"]:
                        self.setCursor(Qt.SizeBDiagCursor)
                else:
                    self.unsetCursor()
        else:
            # If docked or maximized, ensure no resize cursor is ever shown.
            self.unsetCursor()

        # In all cases, pass the event to the superclass for the title bar drag to work.
        super().mouseMoveEvent(event)

    def eventFilter(self, watched, event):
        """
        Filters events from self and child widgets to handle focus and resizing.
        """
        # Handle focus changes to update the shadow color.
        if watched is self:
            if event.type() == QEvent.Type.WindowActivate:
                self._shadow_color = self._shadow_color_focused
                self.update()
                return True
            elif event.type() == QEvent.Type.WindowDeactivate:
                self._shadow_color = self._shadow_color_unfocused
                self.update()
                return True

        # Watch for events coming from the actual content_widget.
        if watched is self.content_widget and event.type() == QEvent.Type.MouseMove:
            if not self.resizing and not self.title_bar.moving:
                # Map the event's position from the child to this widget's coordinates
                mapped_event = QMouseEvent(event.type(), self.mapFrom(watched, event.pos()), event.button(),
                                           event.buttons(), event.modifiers())
                self.mouseMoveEvent(mapped_event)
                return True  # Event is handled

        return super().eventFilter(watched, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.fillRect(self.rect(), Qt.transparent)

        # When maximized, content rect is the full widget. Otherwise, it's inset for the shadow.
        content_rect = self.rect() if self._is_maximized else self.rect().adjusted(
            self._blur_radius, self._blur_radius,
            -self._blur_radius, -self._blur_radius
        )

        # Do not draw shadow if maximized
        if not self._is_maximized:
            painter.setBrush(Qt.NoBrush)
            for i in range(self._blur_radius):
                falloff = 1.0 - (i / self._blur_radius)
                alpha_factor = falloff ** self._feather_power
                alpha = int(self._shadow_color.alpha() * alpha_factor)
                pen_color = QColor(self._shadow_color.red(), self._shadow_color.green(), self._shadow_color.blue(),
                                   alpha)

                pen = painter.pen()
                pen.setColor(pen_color)
                pen.setWidth(1)
                painter.setPen(pen)

                base_corner_radius = 8.0
                current_corner_radius = base_corner_radius + i
                painter.drawRoundedRect(content_rect.adjusted(-i, -i, i, i), current_corner_radius,
                                        current_corner_radius)

        border_color = QColor("#A9A9A9")
        # Use the instance attribute for the title bar background color
        title_bg_color = self._title_bar_color
        content_bg_color = self.original_bg_color if hasattr(self,
                                                             'original_bg_color') and self.original_bg_color else QColor(
            "white")
        radius = 8.0 if not self._is_maximized else 0

        full_path = QPainterPath()
        full_path.addRoundedRect(QRectF(content_rect), radius, radius)

        # Use clipping to restore the rounded corner appearance
        painter.setClipPath(full_path)
        painter.fillRect(content_rect, content_bg_color)
        painter.fillRect(self.title_bar.geometry(), title_bg_color)

        painter.setClipping(False)
        painter.setPen(border_color)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(full_path)

    def setContent(self, widget, margin_size=5):
        self.content_widget = widget
        self.content_widget.setObjectName(f"ActualContent_{self.windowTitle().replace(' ', '_')}")
        self.original_bg_color = widget.palette().color(widget.backgroundRole())
        self.content_container.setStyleSheet("background: transparent;")
        widget.setAutoFillBackground(False)
        widget.setStyleSheet("background: transparent;")
        self.content_layout.setContentsMargins(margin_size, margin_size, margin_size, margin_size)
        self.content_layout.addWidget(widget)
        if self.content_widget:
            self.content_widget.setMouseTracking(True)
            # Install the filter on the actual content widget.
            self.content_widget.installEventFilter(self)
        self.update()

    def getContent(self) -> QWidget | None:
        """
        Returns the content widget that is displayed inside this dockable widget.
        This provides a consistent API with Qt's QDockWidget.
        """
        return getattr(self, 'content_widget', None)

    def get_edge(self, pos):
        # Adjust position to be relative to the visible content area, not the whole window
        adj_pos = pos - QPoint(self._blur_radius, self._blur_radius)
        content_rect = self.rect().adjusted(self._blur_radius, self._blur_radius, -self._blur_radius,
                                            -self._blur_radius)

        # Check only if cursor is within the visible content rect
        if not content_rect.contains(pos):
            return None

        margin = self.resize_margin
        on_left = 0 <= adj_pos.x() < margin
        on_right = content_rect.width() - margin < adj_pos.x() <= content_rect.width()
        on_top = 0 <= adj_pos.y() < margin
        on_bottom = content_rect.height() - margin < adj_pos.y() <= content_rect.height()

        if on_top:
            if on_left: return "top_left"
            if on_right: return "top_right"
            return "top"
        if on_bottom:
            if on_left: return "bottom_left"
            if on_right: return "bottom_right"
            return "bottom"
        if on_left: return "left"
        if on_right: return "right"
        return None


    def show_overlay(self):
        overlay_parent = self.parent_container if self.parent_container else self
        visible_widget = self.content_container
        if not self.overlay or self.overlay.parent() is not overlay_parent:
            if self.overlay: self.overlay.deleteLater()
            self.overlay = DockingOverlay(overlay_parent)
        global_pos = visible_widget.mapToGlobal(QPoint(0, 0))
        parent_local_pos = overlay_parent.mapFromGlobal(global_pos)
        self.overlay.setGeometry(QRect(parent_local_pos, visible_widget.size()))
        self.overlay.show()
        self.overlay.raise_()

    def hide_overlay(self):
        if self.overlay: self.overlay.hide()

    def get_dock_location(self, global_pos):
        if self.overlay:
            pos_in_overlay = self.overlay.mapFromGlobal(global_pos)
            return self.overlay.get_dock_location(pos_in_overlay)
        return None

    def show_preview(self, location):
        if self.overlay: self.overlay.show_preview(location)

    def show(self):
        # This is the new, intelligent show method.
        # If the widget has a manager and a main window is set, we can auto-position it.
        if self.manager and self.manager.main_window:
            # Do not auto-position a widget if it's already maximized or if it already
            # has a valid, non-zero position.
            if not self._is_maximized and self.pos().x() == 0 and self.pos().y() == 0:
                main_window_pos = self.manager.main_window.pos()

                # Use the manager's counter to create a pleasing cascade effect.
                count = self.manager.floating_widget_count
                new_global_x = main_window_pos.x() + 150 + (count % 7) * 40
                new_global_y = main_window_pos.y() + 150 + (count % 7) * 40
                self.move(new_global_x, new_global_y)

        # Call the original QWidget.show() to make the widget visible.
        super().show()

    def set_title(self, new_title: str):
        """
        Updates the title of the dockable widget.
        This changes both the window's official title and the visible text in the title bar.
        """
        self.setWindowTitle(new_title)
        if self.title_bar:
            self.title_bar.title_label.setText(new_title)

    # Close event no longer needs to handle a separate shadow
    def closeEvent(self, event):
        if self.manager:
            if self in self.manager.model.roots:
                self.manager._cleanup_widget_references(self)
                if self.manager.debug_mode:
                    self.manager.model.pretty_print()
        super().closeEvent(event)