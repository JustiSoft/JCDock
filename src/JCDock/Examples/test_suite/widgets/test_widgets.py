"""
Basic test widget classes for the JCDock test suite.
These are simple widgets used for testing basic docking functionality.
"""

from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QTableWidget, QMenu
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from JCDock import dockable
from ..utils.data_generator import DataGenerator
from ..utils.constants import TABLE_ROWS_DEFAULT, TABLE_COLUMNS_DEFAULT


@dockable("test_widget", "Test Widget")
class TestContentWidget(QWidget):
    """Registered widget class for the new registry system with state persistence support."""
    
    def __init__(self, widget_name="Test Widget"):
        super().__init__()
        self.widget_name = widget_name
        
        layout = QVBoxLayout(self)
        
        # Add a label
        self.main_label = QLabel(f"This is {widget_name}")
        self.main_label.setStyleSheet("font-weight: bold; padding: 10px;")
        layout.addWidget(self.main_label)
        
        # Add some buttons
        button1 = QPushButton("Button 1")
        button2 = QPushButton("Button 2") 
        layout.addWidget(button1)
        layout.addWidget(button2)
        
        # Add a table with test data
        self.table = QTableWidget(TABLE_ROWS_DEFAULT, TABLE_COLUMNS_DEFAULT)
        self.table.setHorizontalHeaderLabels(["Item ID", "Description", "Value"])
        
        # Initialize with default data
        self._populate_table()
        layout.addWidget(self.table)
        
        # State persistence tracking
        self.click_count = 0
        self.last_modified = None
        
        # Connect button to demonstrate state persistence
        button1.clicked.connect(self._increment_click_count)
        
    def _populate_table(self, data=None):
        """Populate table with provided data or generate new random data."""
        if data is None:
            # Generate new data using the data generator
            table_data = DataGenerator.generate_table_data(
                TABLE_ROWS_DEFAULT, TABLE_COLUMNS_DEFAULT, self.widget_name
            )
            DataGenerator.populate_table_widget(self.table, table_data)
        else:
            # Restore from saved data
            DataGenerator.populate_table_widget(self.table, data)
    
    def _increment_click_count(self):
        """Increment click count and update the label to show persistent state."""
        self.click_count += 1
        self.last_modified = datetime.now().strftime('%H:%M:%S')
        self.main_label.setText(f"{self.widget_name} - Clicks: {self.click_count} (Last: {self.last_modified})")
    
    def get_dock_state(self):
        """
        Return the widget's internal state for persistence.
        This method will be called during layout serialization.
        """
        # Save table data
        table_data = []
        for row in range(self.table.rowCount()):
            row_data = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                row_data.append(item.text() if item else "")
            table_data.append(row_data)
        
        return {
            'widget_name': self.widget_name,
            'click_count': self.click_count,
            'last_modified': self.last_modified,
            'table_data': table_data
        }
    
    def set_dock_state(self, state_dict):
        """
        Restore the widget's internal state from persistence.
        This method will be called during layout deserialization.
        """
        if not isinstance(state_dict, dict):
            return
        
        # Restore widget properties
        self.widget_name = state_dict.get('widget_name', self.widget_name)
        self.click_count = state_dict.get('click_count', 0)
        self.last_modified = state_dict.get('last_modified', None)
        
        # Update the label to reflect restored state
        if self.click_count > 0 and self.last_modified:
            self.main_label.setText(f"{self.widget_name} - Clicks: {self.click_count} (Last: {self.last_modified})")
        else:
            self.main_label.setText(f"This is {self.widget_name}")
        
        # Restore table data
        table_data = state_dict.get('table_data')
        if table_data:
            self._populate_table(table_data)


@dockable("tab_widget_1", "Tab Widget 1")
class TabWidget1(QWidget):
    """First widget type for tab testing."""
    
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Tab Widget 1 Content"))
        
        regular_button = QPushButton("Tab 1 Button")
        layout.addWidget(regular_button)
        
        tooltip_button = QPushButton("Hover for Tooltip")
        tooltip_button.setToolTip("This is a helpful tooltip that appears when you hover over the button!")
        tooltip_button.clicked.connect(self._on_tooltip_button_clicked)
        layout.addWidget(tooltip_button)
    
    def _on_tooltip_button_clicked(self):
        """Handle tooltip button click."""
        print("Tooltip button clicked!")


@dockable("tab_widget_2", "Tab Widget 2") 
class TabWidget2(QWidget):
    """Second widget type for tab testing."""
    
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Tab Widget 2 Content"))
        
        regular_button = QPushButton("Tab 2 Button")
        layout.addWidget(regular_button)
        
        context_menu_button = QPushButton("Right-click for Menu")
        context_menu_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        context_menu_button.customContextMenuRequested.connect(self._show_context_menu)
        context_menu_button.clicked.connect(self._on_context_menu_button_clicked)
        layout.addWidget(context_menu_button)
        
        self.context_menu_button = context_menu_button
    
    def _on_context_menu_button_clicked(self):
        """Handle context menu button click."""
        print("Context menu button clicked!")
    
    def _show_context_menu(self, position):
        """Show a context menu when right-clicking the button."""
        context_menu = QMenu(self)
        
        action1 = QAction("Option 1", self)
        action1.triggered.connect(lambda: print("Option 1 selected from context menu"))
        context_menu.addAction(action1)
        
        action2 = QAction("Option 2", self)
        action2.triggered.connect(lambda: print("Option 2 selected from context menu"))
        context_menu.addAction(action2)
        
        context_menu.addSeparator()
        
        action3 = QAction("Help", self)
        action3.triggered.connect(lambda: print("Help selected from context menu"))
        context_menu.addAction(action3)
        
        global_pos = self.context_menu_button.mapToGlobal(position)
        context_menu.exec(global_pos)


@dockable("right_widget", "Right Widget")
class RightWidget(QWidget):
    """Widget type for right-side testing."""
    
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Right Widget Content"))
        button = QPushButton("Right Button")
        button.clicked.connect(self._on_right_button_clicked)
        layout.addWidget(button)
    
    def _on_right_button_clicked(self):
        """Handle right button click."""
        print("Right button clicked!")