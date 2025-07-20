from functools import lru_cache
from typing import Optional
from PySide6.QtGui import QIcon, QColor, QPixmap, QPainter, QPen, QPainterPath
from PySide6.QtCore import Qt, QRect, QRectF


class IconCache:
    """
    Centralized icon caching system to eliminate redundant icon creation.
    Uses LRU cache to store frequently used icons and improve performance.
    """
    
    @staticmethod
    @lru_cache(maxsize=50)
    def get_control_icon(icon_type: str, color_hex: str = "#303030", size: int = 24) -> QIcon:
        """
        Creates and caches window control icons (minimize, maximize, restore, close).
        
        Args:
            icon_type: Type of icon ("minimize", "maximize", "restore", "close")
            color_hex: Hex color string for the icon
            size: Size of the icon in pixels
            
        Returns:
            QIcon: Cached or newly created icon
        """
        color = QColor(color_hex)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(color, 1.2)
        painter.setPen(pen)

        # Center the drawing in a 10x10 area inside the pixmap
        margin = (size - 10) // 2
        rect = QRect(margin, margin, 10, 10)

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

    @staticmethod
    @lru_cache(maxsize=50)
    def get_corner_button_icon(icon_type: str, color_hex: str = "#303030", size: int = 18) -> QIcon:
        """
        Creates and caches corner button icons for tab widgets.
        
        Args:
            icon_type: Type of icon ("restore", "close")
            color_hex: Hex color string for the icon
            size: Size of the icon in pixels
            
        Returns:
            QIcon: Cached or newly created icon
        """
        color = QColor(color_hex)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        if icon_type == "restore":
            pen = QPen(color, 1.0)
            painter.setPen(pen)
            # Centered in a 10x10 area, shifted up by 1px for vertical alignment
            margin_x = (size - 10) // 2
            margin_y = (size - 10) // 2 - 1
            rect = QRect(margin_x, margin_y, 10, 10)

            # Draw back window
            painter.drawRect(rect.adjusted(0, 2, -2, 0))

            # Draw front window by erasing the intersection and then drawing the new rect
            front_rect = rect.adjusted(2, 0, 0, -2)
            erase_path = QPainterPath()
            erase_path.addRect(QRectF(front_rect))

            # Use CompositionMode_Clear to "erase" the area under the front window
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillPath(erase_path, Qt.transparent)

            # Switch back to normal drawing mode and draw the front window's outline
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.drawRect(front_rect)

        elif icon_type == "close":
            # A 1.2px pen gives the anti-aliaser enough information to create a smooth line
            pen = QPen(color, 1.2)
            painter.setPen(pen)

            # A 10x10 drawing rect, perfectly centered on the canvas
            margin = (size - 10) // 2
            rect = QRect(margin, margin, 10, 10)

            # Draw the two diagonal lines using the integer corners of the rectangle
            painter.drawLine(rect.topLeft(), rect.bottomRight())
            painter.drawLine(rect.topRight(), rect.bottomLeft())

        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def clear_cache():
        """
        Clears the icon cache to free memory.
        Useful for memory management in long-running applications.
        """
        IconCache.get_control_icon.cache_clear()
        IconCache.get_corner_button_icon.cache_clear()

    @staticmethod
    def cache_info():
        """
        Returns cache statistics for monitoring purposes.
        
        Returns:
            dict: Cache statistics for both icon types
        """
        return {
            'control_icons': IconCache.get_control_icon.cache_info(),
            'corner_button_icons': IconCache.get_corner_button_icon.cache_info()
        }