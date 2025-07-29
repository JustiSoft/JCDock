from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPixmap, QPainter


class DragProxy(QWidget):
    """
    A lightweight proxy widget that displays a screenshot of a container during drag operations.
    This eliminates the need to repaint complex widgets during movement, dramatically improving performance.
    """
    
    def __init__(self, source_widget, parent=None):
        """
        Initialize the drag proxy with a screenshot of the source widget.
        
        Args:
            source_widget: The widget to create a proxy for
            parent: Optional parent widget
        """
        super().__init__(parent)
        
        self.source_widget = source_widget
        self._proxy_pixmap = None
        
        # Set up the proxy widget properties
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(False)  # Don't interfere with drag operations
        
        # Capture the source widget as a pixmap
        self._capture_source_widget()
        
        # Set the proxy size to match the source
        if self._proxy_pixmap:
            self.resize(self._proxy_pixmap.size())
    
    def _capture_source_widget(self):
        """
        Captures the source widget as a QPixmap for display during drag.
        Uses widget.grab() for high-quality screenshot capture.
        """
        if not self.source_widget or not self.source_widget.isVisible():
            return
            
        try:
            # Grab the entire widget including children
            self._proxy_pixmap = self.source_widget.grab()
            
            # Apply slight transparency to indicate drag state
            if not self._proxy_pixmap.isNull():
                # Create a semi-transparent version
                transparent_pixmap = QPixmap(self._proxy_pixmap.size())
                transparent_pixmap.fill(Qt.transparent)
                
                painter = QPainter(transparent_pixmap)
                painter.setOpacity(0.8)  # 80% opacity for drag feedback
                painter.drawPixmap(0, 0, self._proxy_pixmap)
                painter.end()
                
                self._proxy_pixmap = transparent_pixmap
                
        except Exception as e:
            print(f"Warning: Failed to capture drag proxy screenshot: {e}")
            self._proxy_pixmap = None
    
    def paintEvent(self, event):
        """
        Paint the captured pixmap.
        """
        if self._proxy_pixmap and not self._proxy_pixmap.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawPixmap(self.rect(), self._proxy_pixmap)
        
        super().paintEvent(event)
    
    def update_position(self, global_pos):
        """
        Update the proxy position to follow the mouse cursor.
        
        Args:
            global_pos: Global mouse position
        """
        # Position the proxy centered on the cursor
        proxy_pos = global_pos - QPoint(self.width() // 2, 30)  # Offset by title bar height
        self.move(proxy_pos)
    
    def show_proxy(self):
        """
        Show the drag proxy widget.
        """
        if self._proxy_pixmap and not self._proxy_pixmap.isNull():
            self.show()
            self.raise_()
    
    def hide_proxy(self):
        """
        Hide the drag proxy widget.
        """
        self.hide()
    
    def cleanup(self):
        """
        Clean up resources and hide the proxy.
        """
        self.hide()
        self._proxy_pixmap = None
        self.source_widget = None