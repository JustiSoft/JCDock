# dock_panel.py

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout, QStyle, QApplication, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QPoint, QRect, QEvent, QRectF
from PySide6.QtGui import QColor, QPainter, QBrush, QMouseEvent, QPainterPath, QPalette, QRegion, QPen, QIcon, QPixmap
from typing import Union, Optional

from ..interaction.docking_overlay import DockingOverlay
from .title_bar import TitleBar



class DockPanel(QWidget):
    def __init__(self, title, parent=None, manager=None, persistent_id=None, title_bar_color=None):
        super().__init__(parent)

        self.content_widget = None
        self.parent_container = None
        self._content_margin_size = 5

        self.persistent_id = persistent_id

        if title_bar_color is not None:
            self._title_bar_color = title_bar_color
        else:
            self._title_bar_color = QColor("#E0E1E2")

        self.setObjectName(f"DockPanel_{title.replace(' ', '_')}")
        self.setWindowTitle(title)
        self.manager = manager


        self.setFocusPolicy(Qt.StrongFocus)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.title_bar = TitleBar(title, self, top_level_widget=self)
        self.main_layout.addWidget(self.title_bar)

        self.content_container = QWidget()
        self.content_container.setObjectName("ContentContainer")
        self.content_container.setMouseTracking(True)
        self.main_layout.addWidget(self.content_container)

        self.content_layout = QVBoxLayout(self.content_container)
        self.overlay = None

        self.setMinimumSize(300, 200)
        self.resize(300, 200)


        self.is_tabbed = False
        self.setMouseTracking(True)

    def set_title_bar_color(self, new_color: QColor):
        """
        Sets the background color of the widget's title bar.
        """
        self._title_bar_color = new_color
        self.update()
        
            
            


    def on_activation_request(self):
        self.raise_()
        if self.manager:
            self.manager.bring_to_front(self)




    def _reinstall_content_filters(self):
        """Lightweight filter setup - global filter handles coordination."""
        if self.content_widget:
            self.content_widget.setMouseTracking(True)
            if hasattr(self.content_widget, 'viewport'):
                viewport = self.content_widget.viewport()
                if viewport:
                    viewport.setMouseTracking(True)

    def changeEvent(self, event):

        if event.type() == QEvent.Type.ParentChange:
            self._reinstall_content_filters()
        super().changeEvent(event)



    def setContent(self, widget, margin_size=5):
        self._content_margin_size = margin_size
        self.content_widget = widget
        self.content_widget.setObjectName(f"ActualContent_{self.windowTitle().replace(' ', '_')}")
        self.original_bg_color = widget.palette().color(widget.backgroundRole())
        widget.setAutoFillBackground(False)
        self.content_layout.setContentsMargins(margin_size, margin_size, margin_size, margin_size)
        self.content_layout.addWidget(widget)
        if self.content_widget:
            self.content_widget.setMouseTracking(True)
            if hasattr(widget, 'viewport'):
                viewport = widget.viewport()
                if viewport:
                    viewport.setMouseTracking(True)
        
        # Trigger event filter installation on parent container if it exists
        if self.parent_container and hasattr(self.parent_container, '_install_event_filter_recursive'):
            self.parent_container._install_event_filter_recursive(widget)
        
        self.update()

    def showEvent(self, event):
        """
        On show, reinstall the event filters on the content widget. This is
        critical for when this widget becomes a floating window after being
        simplified from a container, as its event handling needs to be refreshed.
        """
        self._reinstall_content_filters()
        super().showEvent(event)

    def show_overlay(self):
        overlay_parent = self.parent_container if self.parent_container else self
        if self.overlay and self.overlay.parent() is not overlay_parent:
            self.overlay.destroy_overlay()
            self.overlay = None
            
        visible_widget = self.content_container
        if not self.overlay:
            try:
                self.overlay = DockingOverlay(overlay_parent)
            except (SystemError, RuntimeError):
                return
            
        global_pos = visible_widget.mapToGlobal(QPoint(0, 0))
        parent_local_pos = overlay_parent.mapFromGlobal(global_pos)
        self.overlay.setGeometry(QRect(parent_local_pos, visible_widget.size()))
        self.overlay.show()
        self.overlay.raise_()

    def hide_overlay(self):
        if self.overlay:
            if hasattr(self.overlay, 'preview_overlay'):
                self.overlay.preview_overlay.hide()
            self.overlay.hide()

    def get_dock_location(self, global_pos):
        if self.overlay:
            pos_in_overlay = self.overlay.mapFromGlobal(global_pos)
            return self.overlay.get_dock_location(pos_in_overlay)
        return None

    def show_preview(self, location):
        if self.overlay: self.overlay.show_preview(location)


    def set_title(self, new_title: str):
        """
        Updates the title of the dock panel.
        This changes both the window's official title and the visible text in the title bar.
        """
        self.setWindowTitle(new_title)
        if self.title_bar:
            self.title_bar.title_label.setText(new_title)
        
        # Notify parent container to update tab text if this panel is tabbed
        self._notify_parent_container_title_changed()

    def set_icon(self, icon: Optional[Union[str, QIcon]]):
        """
        Set or update the dock panel icon.
        This updates both the title bar icon and any parent container tab icon.
        
        Args:
            icon: Icon source - can be file path, Unicode character, Qt standard icon name, or QIcon object
        """
        if self.title_bar:
            self.title_bar.set_icon(icon)
        
        # Notify parent container to update tab icon if this panel is tabbed
        self._notify_parent_container_icon_changed()

    def get_icon(self) -> Optional[QIcon]:
        """
        Get the current icon as a QIcon object.
        
        Returns:
            QIcon: Current icon or None if no icon is set
        """
        if self.title_bar:
            return self.title_bar.get_icon()
        return None

    def has_icon(self) -> bool:
        """
        Check if the dock panel currently has an icon.
        
        Returns:
            bool: True if panel has an icon, False otherwise
        """
        if self.title_bar:
            return self.title_bar.has_icon()
        return False

    def _notify_parent_container_icon_changed(self):
        """
        Notify the parent container that this panel's icon has changed.
        This allows the container to update the corresponding tab icon AND
        if this is a single widget, update the container's title bar icon.
        """
        from .dock_container import DockContainer
        
        if self.parent_container and isinstance(self.parent_container, DockContainer):
            # Update tab icon if this widget is in a tab group
            if hasattr(self.parent_container, 'update_tab_icon'):
                self.parent_container.update_tab_icon(self)
            
            # If this is the only widget in the container, also update container title bar
            if len(self.parent_container.contained_widgets) == 1:
                if hasattr(self.parent_container, 'set_icon') and self.parent_container.title_bar:
                    icon = self.get_icon()
                    if icon:
                        self.parent_container.set_icon(icon)
                    else:
                        self.parent_container.set_icon(None)

    def _notify_parent_container_title_changed(self):
        """
        Notify the parent container that this panel's title has changed.
        This allows the container to update the corresponding tab text.
        """
        from .dock_container import DockContainer
        
        if self.parent_container and isinstance(self.parent_container, DockContainer):
            if hasattr(self.parent_container, 'update_tab_text'):
                self.parent_container.update_tab_text(self)

    def closeEvent(self, event):
        if self.manager:
            if self in self.manager.model.roots:
                self.manager._cleanup_widget_references(self)
        super().closeEvent(event)