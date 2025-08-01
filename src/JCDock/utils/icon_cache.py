from functools import lru_cache
from typing import Optional, Union
from pathlib import Path
from PySide6.QtGui import QIcon, QColor, QPixmap, QPainter, QPen, QPainterPath, QFont, QFontMetrics
from PySide6.QtCore import Qt, QRect, QRectF
from PySide6.QtWidgets import QStyle, QApplication


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

        margin = (size - 10) // 2
        rect = QRect(margin, margin, 10, 10)

        if icon_type == "minimize":
            painter.drawLine(rect.left(), rect.center().y() + 1, rect.right(), rect.center().y() + 1)
        elif icon_type == "maximize":
            painter.drawRect(rect)
        elif icon_type == "restore":
            painter.drawRect(rect.adjusted(0, 2, -2, 0))
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
            margin_x = (size - 10) // 2
            margin_y = (size - 10) // 2 - 1
            rect = QRect(margin_x, margin_y, 10, 10)

            painter.drawRect(rect.adjusted(0, 2, -2, 0))

            front_rect = rect.adjusted(2, 0, 0, -2)
            erase_path = QPainterPath()
            erase_path.addRect(QRectF(front_rect))

            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillPath(erase_path, Qt.transparent)

            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.drawRect(front_rect)

        elif icon_type == "close":
            pen = QPen(color, 1.2)
            painter.setPen(pen)

            margin = (size - 10) // 2
            rect = QRect(margin, margin, 10, 10)

            painter.drawLine(rect.topLeft(), rect.bottomRight())
            painter.drawLine(rect.topRight(), rect.bottomLeft())

        painter.end()
        return QIcon(pixmap)

    @staticmethod
    @lru_cache(maxsize=100)
    def get_custom_icon(icon_source: Union[str, QIcon], size: int = 24, color_hex: str = "#303030") -> Optional[QIcon]:
        """
        Creates and caches custom icons from various sources.
        
        Args:
            icon_source: Icon source - can be:
                        - File path (PNG, JPG, JPEG, ICO, SVG)
                        - Unicode character/emoji (single character)
                        - Qt standard icon name (e.g., "SP_FileIcon")
                        - QIcon object (returned as-is)
            size: Target size for the icon in pixels (max 32)
            color_hex: Color for Unicode character icons
            
        Returns:
            QIcon: Processed icon or None if invalid/failed
        """
        # Limit size to reasonable maximum
        size = min(size, 32)
        
        # Handle QIcon objects directly
        if isinstance(icon_source, QIcon):
            return icon_source
        
        if not isinstance(icon_source, str) or not icon_source.strip():
            return None
            
        icon_source = icon_source.strip()
        
        # Handle file paths
        if '/' in icon_source or '\\' in icon_source or '.' in icon_source:
            return IconCache._create_file_icon(icon_source, size)
        
        # Handle Qt Standard Icons
        if icon_source.startswith('SP_'):
            return IconCache._create_standard_icon(icon_source, size)
        
        # Handle Unicode characters (single character)
        if len(icon_source) == 1:
            return IconCache._create_unicode_icon(icon_source, size, color_hex)
        
        # Handle multi-character strings as potential emoji sequences
        if len(icon_source) <= 10:  # Reasonable limit for emoji sequences
            return IconCache._create_unicode_icon(icon_source, size, color_hex)
            
        return None

    @staticmethod
    def _create_file_icon(file_path: str, size: int) -> Optional[QIcon]:
        """Create icon from file path."""
        try:
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                return None
                
            # Check supported formats
            supported_formats = {'.png', '.jpg', '.jpeg', '.ico', '.svg', '.bmp', '.gif'}
            if path.suffix.lower() not in supported_formats:
                return None
                
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                return None
                
            # Scale to target size if needed
            if pixmap.width() > size or pixmap.height() > size:
                pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                
            return QIcon(pixmap)
        except Exception:
            return None

    @staticmethod
    def _create_standard_icon(icon_name: str, size: int) -> Optional[QIcon]:
        """Create icon from Qt standard icon name."""
        try:
            app = QApplication.instance()
            if not app:
                return None
                
            style = app.style()
            if not style:
                return None
                
            # Map string names to QStyle.StandardPixmap enum values
            standard_icons = {
                'SP_FileIcon': QStyle.StandardPixmap.SP_FileIcon,
                'SP_DirIcon': QStyle.StandardPixmap.SP_DirIcon,
                'SP_ComputerIcon': QStyle.StandardPixmap.SP_ComputerIcon,
                'SP_DesktopIcon': QStyle.StandardPixmap.SP_DesktopIcon,
                'SP_TrashIcon': QStyle.StandardPixmap.SP_TrashIcon,
                'SP_FileDialogDetailedView': QStyle.StandardPixmap.SP_FileDialogDetailedView,
                'SP_FileDialogInfoView': QStyle.StandardPixmap.SP_FileDialogInfoView,
                'SP_FileDialogListView': QStyle.StandardPixmap.SP_FileDialogListView,
                'SP_DialogOkButton': QStyle.StandardPixmap.SP_DialogOkButton,
                'SP_DialogCancelButton': QStyle.StandardPixmap.SP_DialogCancelButton,
                'SP_DialogHelpButton': QStyle.StandardPixmap.SP_DialogHelpButton,
                'SP_DialogOpenButton': QStyle.StandardPixmap.SP_DialogOpenButton,
                'SP_DialogSaveButton': QStyle.StandardPixmap.SP_DialogSaveButton,
                'SP_ArrowUp': QStyle.StandardPixmap.SP_ArrowUp,
                'SP_ArrowDown': QStyle.StandardPixmap.SP_ArrowDown,
                'SP_ArrowLeft': QStyle.StandardPixmap.SP_ArrowLeft,
                'SP_ArrowRight': QStyle.StandardPixmap.SP_ArrowRight
            }
            
            if icon_name in standard_icons:
                return style.standardIcon(standard_icons[icon_name])
        except Exception:
            pass
        return None

    @staticmethod
    def _create_unicode_icon(unicode_char: str, size: int, color_hex: str) -> Optional[QIcon]:
        """Create icon from Unicode character or emoji."""
        try:
            color = QColor(color_hex)
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            
            # Use system default font, scaled to fit
            font = QFont()
            font.setPixelSize(int(size * 0.8))  # 80% of size to leave some margin
            painter.setFont(font)
            painter.setPen(color)
            
            # Center the character
            rect = QRect(0, 0, size, size)
            painter.drawText(rect, Qt.AlignCenter, unicode_char)
            
            painter.end()
            return QIcon(pixmap)
        except Exception:
            return None

    @staticmethod
    def clear_cache():
        """
        Clears the icon cache to free memory.
        Useful for memory management in long-running applications.
        """
        IconCache.get_control_icon.cache_clear()
        IconCache.get_corner_button_icon.cache_clear()
        IconCache.get_custom_icon.cache_clear()

    @staticmethod
    def cache_info():
        """
        Returns cache statistics for monitoring purposes.
        
        Returns:
            dict: Cache statistics for all icon types
        """
        return {
            'control_icons': IconCache.get_control_icon.cache_info(),
            'corner_button_icons': IconCache.get_corner_button_icon.cache_info(),
            'custom_icons': IconCache.get_custom_icon.cache_info()
        }