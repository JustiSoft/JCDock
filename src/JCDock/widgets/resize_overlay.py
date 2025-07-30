from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor, QPen


class ResizeOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Make this a top-level overlay widget
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        
        # Semi-transparent overlay color
        self._overlay_color = QColor(100, 150, 200, 80)  # Light blue with transparency
        self._border_color = QColor(100, 150, 200, 150)  # Slightly more opaque border
        
        # Store original geometry for reference
        self._original_geometry = QRect()
        
    def set_original_geometry(self, geometry: QRect):
        """Set the original geometry of the container being resized."""
        self._original_geometry = QRect(geometry)
        self.setGeometry(geometry)
        
    def update_overlay_geometry(self, new_geometry: QRect):
        """Update the overlay's geometry during resize operations."""
        self.setGeometry(new_geometry)
        self.update()  # Trigger repaint
        
    def paintEvent(self, event):
        """Paint the overlay with a semi-transparent fill and border."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        
        # Fill with semi-transparent color
        painter.fillRect(rect, self._overlay_color)
        
        # Draw border
        pen = QPen(self._border_color, 2)
        painter.setPen(pen)
        painter.drawRect(rect.adjusted(1, 1, -1, -1))
        
    def show_overlay(self):
        """Show the overlay and bring it to the front."""
        self.show()
        self.raise_()
        
        # Ensure overlay stays on top of all other windows
        if self.parent():
            self.activateWindow()
        
    def hide_overlay(self):
        """Hide the overlay."""
        self.hide()