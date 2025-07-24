from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPixmap, QFont, QFontMetrics, QLinearGradient


class TabDragPreview(QWidget):
    """
    Floating transparent preview window that follows the mouse cursor during tab drag operations.
    Provides visual feedback without using Qt's native drag system.
    """
    
    def __init__(self, tab_widget, tab_index, parent=None):
        super().__init__(parent)
        self.tab_widget = tab_widget
        self.tab_index = tab_index
        self.tab_rect = tab_widget.tabBar().tabRect(tab_index)
        
        # Configure window for transparent floating behavior
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool |
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        
        # Size the preview window with margins for effects
        self.margin = 12
        preview_size = self.tab_rect.size()
        preview_size.setWidth(preview_size.width() + self.margin * 2)
        preview_size.setHeight(preview_size.height() + self.margin * 2)
        self.resize(preview_size)
        
        # Cache the tab content pixmap for performance
        self._cache_tab_content()
        
    def _cache_tab_content(self):
        """
        Create a clean, custom tab rendering without artifacts.
        """
        if self.tab_rect.isEmpty():
            self.tab_pixmap = QPixmap()
            return
            
        # Extract clean tab information
        tab_text = self.tab_widget.tabText(self.tab_index)
        tab_icon = self.tab_widget.tabIcon(self.tab_index)
        
        # Create pixmap with clean dimensions
        tab_size = self.tab_rect.size()
        self.tab_pixmap = QPixmap(tab_size)
        self.tab_pixmap.fill(Qt.transparent)
        
        painter = QPainter(self.tab_pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        
        # Create clean tab background with gradient
        tab_rect = QRect(0, 0, tab_size.width(), tab_size.height())
        
        # Modern tab gradient background
        gradient = QLinearGradient(0, 0, 0, tab_rect.height())
        gradient.setColorAt(0, QColor(245, 245, 245))  # Light top
        gradient.setColorAt(1, QColor(235, 235, 235))  # Slightly darker bottom
        
        painter.fillRect(tab_rect, gradient)
        
        # Clean tab border
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawRoundedRect(tab_rect.adjusted(0, 0, -1, -1), 3, 3)
        
        # Draw icon if present
        icon_x = 8
        if not tab_icon.isNull():
            icon_size = 16
            icon_y = (tab_rect.height() - icon_size) // 2
            icon_rect = QRect(icon_x, icon_y, icon_size, icon_size)
            tab_icon.paint(painter, icon_rect)
            icon_x += icon_size + 4
        
        # Draw clean text
        if tab_text:
            font = QFont()
            font.setPixelSize(12)
            font.setFamily("Segoe UI")
            painter.setFont(font)
            
            # Calculate text position
            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(tab_text)
            text_height = metrics.height()
            
            # Center text vertically, position after icon
            text_x = icon_x
            text_y = (tab_rect.height() + text_height) // 2 - 2
            
            # Ensure text fits in available space
            available_width = tab_rect.width() - text_x - 8
            if text_width > available_width:
                tab_text = metrics.elidedText(tab_text, Qt.ElideRight, available_width)
            
            # Draw text with clean color
            painter.setPen(QColor(50, 50, 50))  # Dark gray text
            painter.drawText(text_x, text_y, tab_text)
        
        painter.end()
    
    def update_position(self, global_pos):
        """
        Update the preview window position to follow the mouse cursor.
        
        Args:
            global_pos: Global mouse position (QPoint)
        """
        # Center the preview on the cursor with slight offset
        preview_pos = global_pos - QPoint(self.width() // 2, self.height() // 3)
        self.move(preview_pos)
    
    def paintEvent(self, event):
        """
        Custom paint event to draw the enhanced tab preview with floating effects.
        """
        if self.tab_pixmap.isNull():
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        # Draw enhanced shadow
        shadow_offset = 4
        shadow_rect = QRect(
            self.margin + shadow_offset, 
            self.margin + shadow_offset,
            self.tab_rect.width(), 
            self.tab_rect.height()
        )
        
        # Multi-layer shadow for depth
        shadow_colors = [
            QColor(0, 0, 0, 60),
            QColor(0, 0, 0, 40), 
            QColor(0, 0, 0, 20)
        ]
        
        for i, color in enumerate(shadow_colors):
            offset_rect = shadow_rect.adjusted(i, i, i, i)
            painter.fillRect(offset_rect, color)
        
        # Draw floating window frame
        frame_rect = QRect(self.margin, self.margin, self.tab_rect.width(), self.tab_rect.height())
        
        # Gradient background for floating effect
        background_color = QColor(250, 250, 250, 240)
        painter.fillRect(frame_rect, background_color)
        
        # Draw window frame border
        frame_pen = QPen(QColor(70, 130, 200, 200), 2)
        painter.setPen(frame_pen)
        painter.drawRect(frame_rect)
        
        # Draw the actual tab content with slight transparency
        painter.setOpacity(0.9)
        painter.drawPixmap(QPoint(self.margin, self.margin), self.tab_pixmap)
        
        # Add floating window indicator
        painter.setOpacity(1.0)
        self._draw_floating_indicator(painter, frame_rect)
        
    def _draw_floating_indicator(self, painter, frame_rect):
        """
        Draw a small window icon to indicate this will create a floating window.
        """
        indicator_size = 16
        indicator_rect = QRect(
            frame_rect.right() - indicator_size - 4,
            frame_rect.top() + 4,
            indicator_size,
            indicator_size
        )
        
        # Draw mini window icon
        window_pen = QPen(QColor(70, 130, 200), 2)
        painter.setPen(window_pen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
        painter.drawRect(indicator_rect)
        
        # Draw title bar
        title_rect = QRect(
            indicator_rect.x() + 1,
            indicator_rect.y() + 1,
            indicator_rect.width() - 2,
            4
        )
        painter.fillRect(title_rect, QColor(70, 130, 200))
        
        # Draw minimize/close buttons (tiny dots)
        button_size = 2
        close_pos = QPoint(indicator_rect.right() - 3, indicator_rect.top() + 2)
        minimize_pos = QPoint(indicator_rect.right() - 7, indicator_rect.top() + 2)
        
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.drawEllipse(close_pos, button_size, button_size)
        painter.drawEllipse(minimize_pos, button_size, button_size)
    
    def show_preview(self, global_pos):
        """
        Show the preview window at the specified global position.
        """
        self.update_position(global_pos)
        self.show()
        self.raise_()
    
    def hide_preview(self):
        """
        Hide the preview window.
        """
        self.hide()