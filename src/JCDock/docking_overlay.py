from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import Qt, QRect


class DockingOverlay(QWidget):
    def __init__(self, parent=None, icons=None, color="lightgray", style='cluster'):
        """
        Initializes the overlay.
        :param parent: The parent widget.
        :param icons: A list of strings specifying which icons to show. e.g., ["top", "center"]. If None, all are shown.
        :param color: The background color for the icons.
        :param style: The layout style for the icons ('cluster' or 'spread').
        """
        super().__init__(parent)

        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet("background-color: rgba(0, 0, 255, 0);")
        self.style = style

        if icons is None:
            icons = ["top", "left", "bottom", "right", "center"]

        self.icon_size = 40
        self.dock_icons = {}

        icon_properties = {
            "top": {"text": "⬒", "font-size": "24px"},
            "left": {"text": "◧", "font-size": "35px"},
            "bottom": {"text": "⬓", "font-size": "24px"},
            "right": {"text": "◨", "font-size": "35px"},
            "center": {"text": "⧉", "font-size": "20px"},
        }

        for key in icons:
            if key in icon_properties:
                props = icon_properties[key]
                icon = QLabel(props["text"], self)
                icon.setAlignment(Qt.AlignCenter)
                icon.setStyleSheet(
                    f"background-color: {color}; border: 1px solid black; font-size: {props['font-size']};")
                icon.setFixedSize(self.icon_size, self.icon_size)
                icon.setAttribute(Qt.WA_TranslucentBackground, False)
                self.dock_icons[key] = icon

        try:
            self.preview_overlay = QWidget(self)
            self.preview_overlay.setStyleSheet("background-color: rgba(0, 0, 255, 128);")
            self.preview_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.preview_overlay.hide()
        except (SystemError, RuntimeError):
            self.preview_overlay = None

    def destroy_overlay(self):
        """
        A safe and explicit cleanup method that guarantees complete destruction of
        the overlay and all its child components. This is the ultimate cleanup method.
        """
        try:
            # CRITICAL: Capture parent and geometry BEFORE any destruction to force repaint
            parent = self.parentWidget()
            geom = self.geometry()  # Get the geometry BEFORE reparenting
            
            # First, explicitly hide and destroy the preview widget (the blue area)
            if hasattr(self, 'preview_overlay') and self.preview_overlay:
                self.preview_overlay.hide()
                self.preview_overlay.setParent(None)
                self.preview_overlay.deleteLater()
                self.preview_overlay = None
                
            # Hide and destroy all dock icons
            if hasattr(self, 'dock_icons'):
                for icon in self.dock_icons.values():
                    if icon:
                        icon.hide()
                        icon.setParent(None)
                        icon.deleteLater()
                self.dock_icons.clear()
                
            # Hide the main overlay widget itself
            self.hide()
            
            # Critical: Remove from parent before deletion to prevent orphaning
            self.setParent(None)
            
            # Schedule for deletion by Qt's event loop
            self.deleteLater()
            
            # FORCE REPAINT: Tell the original parent to repaint the area we occupied
            if parent and not (hasattr(parent, 'isDeleted') and parent.isDeleted()):
                parent.update(geom)  # Repaint specific area
                parent.repaint()     # Force immediate repaint
            
        except RuntimeError:
            # Widget may already be deleted - this is acceptable
            pass

    def reposition_icons(self):
        """
        Repositions the dock icons based on the current size of the overlay
        and the specified style.
        """
        overlay_rect = self.rect()
        icon_size = self.icon_size
        center_x = overlay_rect.center().x()
        center_y = overlay_rect.center().y()

        if self.style == 'cluster':
            # Positions icons in a balanced cluster around the center.
            spacing = 5
            center_icon_x = center_x - icon_size / 2
            center_icon_y = center_y - icon_size / 2

            if "center" in self.dock_icons: self.dock_icons["center"].move(center_icon_x, center_icon_y)
            if "top" in self.dock_icons: self.dock_icons["top"].move(center_icon_x, center_icon_y - icon_size - spacing)
            if "bottom" in self.dock_icons: self.dock_icons["bottom"].move(center_icon_x,
                                                                           center_icon_y + icon_size + spacing)
            if "left" in self.dock_icons: self.dock_icons["left"].move(center_icon_x - icon_size - spacing,
                                                                       center_icon_y)
            if "right" in self.dock_icons: self.dock_icons["right"].move(center_icon_x + icon_size + spacing,
                                                                         center_icon_y)
        else:  # 'spread' style
            # Positions icons near the edges of the overlay.
            if "top" in self.dock_icons: self.dock_icons["top"].move(center_x - icon_size / 2, 10)
            if "left" in self.dock_icons: self.dock_icons["left"].move(10, center_y - icon_size / 2)
            if "bottom" in self.dock_icons: self.dock_icons["bottom"].move(center_x - icon_size / 2,
                                                                           overlay_rect.bottom() - icon_size - 10)
            if "right" in self.dock_icons: self.dock_icons["right"].move(overlay_rect.right() - icon_size - 10,
                                                                         center_y - icon_size / 2)
            if "center" in self.dock_icons: self.dock_icons["center"].move(center_x - icon_size / 2,
                                                                           center_y - icon_size / 2)

    def resizeEvent(self, event):
        """ Called when the overlay is resized. Repositions the icons. """
        self.reposition_icons()
        super().resizeEvent(event)

    def get_dock_location(self, pos):
        for location, icon in self.dock_icons.items():
            if icon.geometry().contains(pos):
                return location
        return None

    def show_preview(self, location):
        if not self.preview_overlay:
            return
        if location is None:
            self.preview_overlay.hide()
            return

        overlay_rect = self.rect()
        new_geom = None

        if location == "top":
            new_geom = QRect(0, 0, overlay_rect.width(), overlay_rect.height() // 2)
        elif location == "left":
            new_geom = QRect(0, 0, overlay_rect.width() // 2, overlay_rect.height())
        elif location == "bottom":
            new_geom = QRect(0, overlay_rect.height() // 2, overlay_rect.width(), overlay_rect.height() // 2)
        elif location == "right":
            new_geom = QRect(overlay_rect.width() // 2, 0, overlay_rect.width() // 2, overlay_rect.height())
        elif location == "center":
            new_geom = QRect(overlay_rect)

        if new_geom:
            self.preview_overlay.setGeometry(new_geom)
            self.preview_overlay.show()
        else:
            self.preview_overlay.hide()

    def hide_preview(self):
        if self.preview_overlay and self.preview_overlay.isVisible():
            self.preview_overlay.hide()
            parent = self.parentWidget()
            if parent and not (hasattr(parent, 'isDeleted') and parent.isDeleted()):
                # Force immediate repaint to remove blue preview artifacts
                parent.update()
                parent.repaint()
