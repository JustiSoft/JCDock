# dock_panel.py

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout, QStyle, QApplication, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QPoint, QRect, QEvent, QRectF
from PySide6.QtGui import QColor, QPainter, QBrush, QMouseEvent, QPainterPath, QPalette, QRegion, QPen, QIcon, QPixmap

from .docking_overlay import DockingOverlay
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
        self.installEventFilter(self)

    def set_title_bar_color(self, new_color: QColor):
        """
        Sets the background color of the widget's title bar.
        """
        self._title_bar_color = new_color
        self.update()  # Trigger a repaint to show the new color
        
            
            


    def on_activation_request(self):
        self.raise_()
        if self.manager:
            self.manager.bring_to_front(self)




    def _reinstall_content_filters(self):

        if self.content_widget:
            self.content_widget.installEventFilter(self)
            if hasattr(self.content_widget, 'viewport'):
                viewport = self.content_widget.viewport()
                if viewport:
                    viewport.installEventFilter(self)

    def changeEvent(self, event):

        if event.type() == QEvent.Type.ParentChange:
            self._reinstall_content_filters()
        super().changeEvent(event)

    def eventFilter(self, watched, event):
        """
        Filters events from self and child widgets.
        """
        return super().eventFilter(watched, event)


    def setContent(self, widget, margin_size=5):
        self._content_margin_size = margin_size
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
            self.content_widget.installEventFilter(self)
            if hasattr(widget, 'viewport'):
                viewport = widget.viewport()
                if viewport:
                    viewport.setMouseTracking(True)
                    viewport.installEventFilter(self)
        self.update()

    def getContent(self) -> QWidget | None:
        """
        Returns the content widget that is displayed inside this dock panel.
        This provides a consistent API with Qt's QDockWidget.
        """
        return getattr(self, 'content_widget', None)


    def showEvent(self, event):
        """
        On show, reinstall the event filters on the content widget. This is
        critical for when this widget becomes a floating window after being
        simplified from a container, as its event handling needs to be refreshed.
        """
        self._reinstall_content_filters()
        # The existing show() method in the provided code handles auto-positioning.
        # We call the superclass's showEvent to ensure default Qt behavior.
        super().showEvent(event)

    def show_overlay(self):
        # Always destroy old overlay if parent changes
        overlay_parent = self.parent_container if self.parent_container else self
        if self.overlay and self.overlay.parent() is not overlay_parent:
            self.overlay.destroy_overlay()
            self.overlay = None
            
        visible_widget = self.content_container
        if not self.overlay:
            self.overlay = DockingOverlay(overlay_parent)
            
        global_pos = visible_widget.mapToGlobal(QPoint(0, 0))
        parent_local_pos = overlay_parent.mapFromGlobal(global_pos)
        self.overlay.setGeometry(QRect(parent_local_pos, visible_widget.size()))
        self.overlay.show()
        self.overlay.raise_()

    def hide_overlay(self):
        if self.overlay: 
            # Explicitly hide the preview overlay first to prevent stuck blue areas
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

    # Close event no longer needs to handle a separate shadow
    def closeEvent(self, event):
        if self.manager:
            if self in self.manager.model.roots:
                self.manager._cleanup_widget_references(self)
        super().closeEvent(event)