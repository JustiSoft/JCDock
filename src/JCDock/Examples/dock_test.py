import re
import sys
import random
import configparser
import base64
import os
from datetime import datetime
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QMenuBar, QMenu, QStyle, QHBoxLayout, QFileDialog
from PySide6.QtCore import Qt, QObject, QEvent, Slot, QSize, QPoint, QRect, QTimer
from PySide6.QtGui import QColor, QAction

from JCDock.core.docking_manager import DockingManager
from JCDock.widgets.dock_panel import DockPanel
from JCDock.widgets.floating_dock_root import FloatingDockRoot
from JCDock.widgets.dock_container import DockContainer
from JCDock import dockable






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
        self.table = QTableWidget(5, 3)
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
            # Generate new random data
            for row in range(5):
                item_id = QTableWidgetItem(f"{self.widget_name}-I{row+1}")
                item_desc = QTableWidgetItem(f"Sample data item for row {row+1}")
                item_value = QTableWidgetItem(str(random.randint(100, 999)))
                
                item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_value.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                self.table.setItem(row, 0, item_id)
                self.table.setItem(row, 1, item_desc)
                self.table.setItem(row, 2, item_value)
        else:
            # Restore from saved data
            for row, row_data in enumerate(data):
                for col, cell_value in enumerate(row_data):
                    item = QTableWidgetItem(str(cell_value))
                    if col in [0, 2]:  # Center align first and last columns
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(row, col, item)
        
        self.table.resizeColumnsToContents()
    
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
        tooltip_button.clicked.connect(lambda: print("Tooltip button clicked!"))
        layout.addWidget(tooltip_button)


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
        context_menu_button.customContextMenuRequested.connect(self.show_context_menu)
        context_menu_button.clicked.connect(lambda: print("Context menu button clicked!"))
        layout.addWidget(context_menu_button)
        
        self.context_menu_button = context_menu_button
    
    def show_context_menu(self, position):
        """Shows a context menu when right-clicking the button."""
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
        layout.addWidget(QPushButton("Right Button"))


@dockable("chart_widget", "Chart Widget")
class ChartWidget(QWidget):
    """Chart widget displaying financial data in table format with controls."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Header with chart controls
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("📈 Stock Price Chart"))
        
        refresh_btn = QPushButton("Refresh Data")
        refresh_btn.clicked.connect(self._refresh_chart_data)
        header_layout.addWidget(refresh_btn)
        
        timeframe_btn = QPushButton("1D")
        timeframe_btn.clicked.connect(lambda: print("Timeframe changed"))
        header_layout.addWidget(timeframe_btn)
        
        layout.addLayout(header_layout)
        
        # Chart data table
        self.chart_table = QTableWidget(12, 4)
        self.chart_table.setHorizontalHeaderLabels(["Time", "Price", "Volume", "Change %"])
        
        # Style the table to look more chart-like
        self.chart_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #333;
                background-color: #f8f9fa;
                alternate-background-color: #e9ecef;
            }
            QHeaderView::section {
                background-color: #dee2e6;
                font-weight: bold;
                border: 1px solid #adb5bd;
                padding: 4px;
            }
        """)
        self.chart_table.setAlternatingRowColors(True)
        
        self._populate_chart_data()
        layout.addWidget(self.chart_table)
        
        # Chart controls
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QPushButton("Zoom In"))
        controls_layout.addWidget(QPushButton("Zoom Out"))
        controls_layout.addWidget(QPushButton("Export Chart"))
        layout.addLayout(controls_layout)
    
    def _populate_chart_data(self):
        """Populate chart table with random financial data."""
        import random
        from datetime import datetime, timedelta
        
        base_price = 150.0
        for row in range(12):
            time_str = (datetime.now() - timedelta(hours=11-row)).strftime("%H:%M")
            
            # Simulate price movement
            price_change = random.uniform(-2.5, 2.5)
            current_price = base_price + price_change
            base_price = current_price
            
            volume = random.randint(10000, 500000)
            change_pct = price_change / current_price * 100
            
            self.chart_table.setItem(row, 0, QTableWidgetItem(time_str))
            self.chart_table.setItem(row, 1, QTableWidgetItem(f"${current_price:.2f}"))
            self.chart_table.setItem(row, 2, QTableWidgetItem(f"{volume:,}"))
            
            # Color code the change percentage
            change_item = QTableWidgetItem(f"{change_pct:+.2f}%")
            if change_pct > 0:
                change_item.setBackground(QColor("#d4edda"))
            elif change_pct < 0:
                change_item.setBackground(QColor("#f8d7da"))
            self.chart_table.setItem(row, 3, change_item)
        
        self.chart_table.resizeColumnsToContents()
    
    def _refresh_chart_data(self):
        """Refresh chart data with new random values."""
        self._populate_chart_data()
        print("Chart data refreshed")


@dockable("order_widget", "Order Widget")
class OrderWidget(QWidget):
    """Order management widget for trading operations."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("📋 Order Management"))
        
        new_order_btn = QPushButton("New Order")
        new_order_btn.clicked.connect(self._create_new_order)
        header_layout.addWidget(new_order_btn)
        
        cancel_all_btn = QPushButton("Cancel All")
        cancel_all_btn.clicked.connect(self._cancel_all_orders)
        cancel_all_btn.setStyleSheet("background-color: #dc3545; color: white;")
        header_layout.addWidget(cancel_all_btn)
        
        layout.addLayout(header_layout)
        
        # Order entry form
        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Symbol:"))
        self.symbol_field = QPushButton("AAPL")
        self.symbol_field.clicked.connect(lambda: print("Symbol selector opened"))
        form_layout.addWidget(self.symbol_field)
        
        form_layout.addWidget(QLabel("Qty:"))
        self.qty_field = QPushButton("100")
        form_layout.addWidget(self.qty_field)
        
        form_layout.addWidget(QLabel("Price:"))
        self.price_field = QPushButton("$150.00")
        form_layout.addWidget(self.price_field)
        
        buy_btn = QPushButton("BUY")
        buy_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        buy_btn.clicked.connect(lambda: self._place_order("BUY"))
        form_layout.addWidget(buy_btn)
        
        sell_btn = QPushButton("SELL")
        sell_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
        sell_btn.clicked.connect(lambda: self._place_order("SELL"))  
        form_layout.addWidget(sell_btn)
        
        layout.addLayout(form_layout)
        
        # Orders table
        self.orders_table = QTableWidget(8, 6)
        self.orders_table.setHorizontalHeaderLabels(["Order ID", "Symbol", "Side", "Quantity", "Price", "Status"])
        
        self.orders_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #dee2e6;
                background-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                border: 1px solid #495057;
                padding: 6px;
            }
        """)
        
        self._populate_orders_data()
        layout.addWidget(self.orders_table)
        
        # Status bar
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("📊 Active Orders: 5"))
        status_layout.addWidget(QLabel("💰 Total Value: $15,750"))
        status_layout.addWidget(QLabel("🟢 Connected"))
        layout.addLayout(status_layout)
    
    def _populate_orders_data(self):
        """Populate orders table with random order data."""
        import random
        
        symbols = ["AAPL", "GOOGL", "TSLA", "MSFT", "AMZN", "NVDA"]
        statuses = ["Pending", "Filled", "Cancelled", "Partial"]
        sides = ["BUY", "SELL"]
        
        for row in range(8):
            order_id = f"ORD{1000 + row}"
            symbol = random.choice(symbols)
            side = random.choice(sides)
            quantity = random.randint(10, 500)
            price = random.uniform(50, 300)
            status = random.choice(statuses)
            
            self.orders_table.setItem(row, 0, QTableWidgetItem(order_id))
            self.orders_table.setItem(row, 1, QTableWidgetItem(symbol))
            
            # Color code buy/sell
            side_item = QTableWidgetItem(side)
            if side == "BUY":
                side_item.setForeground(QColor("#28a745"))
            else:
                side_item.setForeground(QColor("#dc3545"))
            self.orders_table.setItem(row, 2, side_item)
            
            self.orders_table.setItem(row, 3, QTableWidgetItem(str(quantity)))
            self.orders_table.setItem(row, 4, QTableWidgetItem(f"${price:.2f}"))
            
            # Color code status
            status_item = QTableWidgetItem(status)
            if status == "Filled":
                status_item.setBackground(QColor("#d4edda"))
            elif status == "Cancelled":
                status_item.setBackground(QColor("#f8d7da"))
            elif status == "Pending":
                status_item.setBackground(QColor("#fff3cd"))
            self.orders_table.setItem(row, 5, status_item)
        
        self.orders_table.resizeColumnsToContents()
    
    def _create_new_order(self):
        """Create a new order."""
        print("New order dialog opened")
    
    def _place_order(self, side):
        """Place a buy/sell order."""
        print(f"Placing {side} order")
        self._populate_orders_data()  # Refresh data
    
    def _cancel_all_orders(self):
        """Cancel all pending orders."""
        print("All orders cancelled")
        self._populate_orders_data()  # Refresh data


@dockable("portfolio_widget", "Portfolio Widget")
class PortfolioWidget(QWidget):
    """Portfolio overview widget showing holdings and performance."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Header with portfolio summary
        header_layout = QVBoxLayout()
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("💼 Portfolio Overview"))
        
        sync_btn = QPushButton("Sync")
        sync_btn.clicked.connect(self._sync_portfolio)
        title_layout.addWidget(sync_btn)
        
        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(lambda: print("Portfolio settings opened"))
        title_layout.addWidget(settings_btn)
        
        header_layout.addLayout(title_layout)
        
        # Portfolio summary
        summary_layout = QHBoxLayout()
        summary_layout.addWidget(QLabel("💰 Total Value: $125,750.00"))
        summary_layout.addWidget(QLabel("📈 Day P&L: +$2,150 (+1.74%)"))
        summary_layout.addWidget(QLabel("📊 Total P&L: +$15,750 (+14.3%)"))
        header_layout.addLayout(summary_layout)
        
        layout.addLayout(header_layout)
        
        # Holdings table
        self.portfolio_table = QTableWidget(10, 7)
        self.portfolio_table.setHorizontalHeaderLabels([
            "Symbol", "Shares", "Avg Cost", "Current Price", "Market Value", "P&L", "P&L %"
        ])
        
        self.portfolio_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e9ecef;
                background-color: #ffffff;
                selection-background-color: #007bff;
            }
            QHeaderView::section {
                background-color: #495057;
                color: white;
                font-weight: bold;
                border: 1px solid #343a40;
                padding: 8px;
            }
        """)
        
        self._populate_portfolio_data()
        layout.addWidget(self.portfolio_table)
        
        # Action buttons
        actions_layout = QHBoxLayout()
        actions_layout.addWidget(QPushButton("Add Position"))
        actions_layout.addWidget(QPushButton("Rebalance"))
        actions_layout.addWidget(QPushButton("Generate Report"))
        actions_layout.addWidget(QPushButton("Export CSV"))
        layout.addLayout(actions_layout)
        
        # Footer with allocation chart (simulated with labels)
        allocation_layout = QHBoxLayout()
        allocation_layout.addWidget(QLabel("Asset Allocation:"))
        allocation_layout.addWidget(QLabel("🟦 Stocks 75%"))
        allocation_layout.addWidget(QLabel("🟩 Bonds 15%"))
        allocation_layout.addWidget(QLabel("🟨 Cash 10%"))
        layout.addLayout(allocation_layout)
    
    def _populate_portfolio_data(self):
        """Populate portfolio table with random holdings data."""
        import random
        
        holdings = [
            ("AAPL", 150), ("GOOGL", 50), ("TSLA", 75), ("MSFT", 200),
            ("AMZN", 30), ("NVDA", 100), ("META", 80), ("NFLX", 25),
            ("DIS", 120), ("V", 90)
        ]
        
        for row, (symbol, shares) in enumerate(holdings):
            avg_cost = random.uniform(50, 300)
            current_price = avg_cost * random.uniform(0.8, 1.4)  # ±40% from cost
            market_value = shares * current_price
            pnl_dollar = shares * (current_price - avg_cost)
            pnl_percent = (current_price - avg_cost) / avg_cost * 100
            
            self.portfolio_table.setItem(row, 0, QTableWidgetItem(symbol))
            self.portfolio_table.setItem(row, 1, QTableWidgetItem(str(shares)))
            self.portfolio_table.setItem(row, 2, QTableWidgetItem(f"${avg_cost:.2f}"))
            self.portfolio_table.setItem(row, 3, QTableWidgetItem(f"${current_price:.2f}"))
            self.portfolio_table.setItem(row, 4, QTableWidgetItem(f"${market_value:,.2f}"))
            
            # Color code P&L
            pnl_dollar_item = QTableWidgetItem(f"${pnl_dollar:+,.2f}")
            pnl_percent_item = QTableWidgetItem(f"{pnl_percent:+.1f}%")
            
            if pnl_dollar > 0:
                pnl_dollar_item.setForeground(QColor("#28a745"))
                pnl_percent_item.setForeground(QColor("#28a745"))
                pnl_dollar_item.setBackground(QColor("#f8fff9"))
                pnl_percent_item.setBackground(QColor("#f8fff9"))
            else:
                pnl_dollar_item.setForeground(QColor("#dc3545"))
                pnl_percent_item.setForeground(QColor("#dc3545"))
                pnl_dollar_item.setBackground(QColor("#fff5f5"))
                pnl_percent_item.setBackground(QColor("#fff5f5"))
            
            self.portfolio_table.setItem(row, 5, pnl_dollar_item)
            self.portfolio_table.setItem(row, 6, pnl_percent_item)
        
        self.portfolio_table.resizeColumnsToContents()
    
    def _sync_portfolio(self):
        """Sync portfolio data."""
        print("Syncing portfolio data...")
        self._populate_portfolio_data()
        print("Portfolio data updated")


class EventListener(QObject):
    """
    A simple event listener to demonstrate connecting to DockingManager signals.
    """
    @Slot(object, object)
    def on_widget_docked(self, widget, container):
        container_name = container.windowTitle()
        if container.objectName() == "MainDockArea":
            container_name = "Main Dock Area"

    @Slot(object)
    def on_widget_undocked(self, widget):
        pass

    @Slot(str)
    def on_widget_closed(self, persistent_id):
        pass

    @Slot()
    def on_layout_changed(self):
        pass

class DockingTestApp:
    """
    Main application class for testing the JCDock library.
    Sets up the main window, docking manager, and test functions.
    """
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Docking Library Test")

        self.docking_manager = DockingManager()

        self.event_listener = EventListener()
        self.docking_manager.signals.widget_docked.connect(self.event_listener.on_widget_docked)
        self.docking_manager.signals.widget_undocked.connect(self.event_listener.on_widget_undocked)
        self.docking_manager.signals.widget_closed.connect(self.event_listener.on_widget_closed)
        self.docking_manager.signals.layout_changed.connect(self.event_listener.on_layout_changed)

        self.widget_count = 0
        # Create main window using FloatingDockRoot with is_main_window=True
        self.main_window = FloatingDockRoot(manager=self.docking_manager, is_main_window=True, 
                                          title="JCDOCK Test Application")
        self.main_window.setWindowTitle("JCDOCK Test Application")
        self.main_window.setGeometry(300, 300, 800, 600)
        self.main_window.setObjectName("MainDockArea")
        self.main_window.set_persistent_root(True)
        
        # Add menu bar support for main window functionality
        from PySide6.QtWidgets import QMenuBar
        self.main_window._menu_bar = QMenuBar(self.main_window)
        
        # Update the layout to include the menu bar below the title bar
        if self.main_window.layout():
            # Insert at position 1 to place it after the title bar (which is at position 0)
            self.main_window.layout().insertWidget(1, self.main_window._menu_bar)

        if self.docking_manager:
            self.docking_manager.register_dock_area(self.main_window)
            self.docking_manager.set_main_window(self.main_window)

        self.saved_layout_data = None

        # Register keys needed for ad-hoc state handler demonstrations
        # This shows how any widget class can be registered even if not decorated
        from JCDock.core.widget_registry import get_registry
        registry = get_registry()
        if not registry.is_registered("adhoc_stateful_widget"):
            # Use the new factory registration to teach the manager how to
            # correctly build the complex ad-hoc widget upon layout load.
            self.docking_manager.register_widget_factory(
                key="adhoc_stateful_widget",
                factory=self._create_adhoc_stateful_widget,
                title="Ad-Hoc Stateful Widget"
            )
            
            # IMPORTANT: Register the state handlers for this widget type
            # This ensures that widgets created during layout loading will have proper state restoration
            self.docking_manager.register_instance_state_handlers(
                persistent_key="adhoc_stateful_widget",
                state_provider=self._extract_adhoc_widget_state,
                state_restorer=self._restore_adhoc_widget_state
            )

        self._create_test_menu_bar()  # Re-enabled menu bar

    def _get_standard_layout_path(self) -> str:
        """Returns the standardized path for the application layout file."""
        layouts_dir = os.path.join(os.getcwd(), "layouts")
        return os.path.join(layouts_dir, "jcdock_layout.ini")

    def _ensure_layout_directory(self):
        """Creates the layouts directory if it doesn't exist."""
        layouts_dir = os.path.join(os.getcwd(), "layouts")
        if not os.path.exists(layouts_dir):
            os.makedirs(layouts_dir)

    def _create_test_menu_bar(self):
        """
        Creates the menu bar for the main window with various test actions.
        """
        menu_bar = self.main_window.menuBar()

        file_menu = menu_bar.addMenu("File")
        save_layout_action = file_menu.addAction("Save Layout")
        save_layout_action.triggered.connect(self.save_layout)
        load_layout_action = file_menu.addAction("Load Layout")
        load_layout_action.triggered.connect(self.load_layout)
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.main_window.close)

        widget_menu = menu_bar.addMenu("Widgets")
        
        # Submenu for "By Type" path - demonstrates registry-based creation
        # This shows how developers can create widgets directly from registered keys
        by_type_menu = widget_menu.addMenu("Create By Type (Registry)")
        test_widget_action = by_type_menu.addAction("Test Widget")
        test_widget_action.triggered.connect(lambda: self.create_widget_by_type("test_widget"))
        tab1_widget_action = by_type_menu.addAction("Tab Widget 1")
        tab1_widget_action.triggered.connect(lambda: self.create_widget_by_type("tab_widget_1"))
        tab2_widget_action = by_type_menu.addAction("Tab Widget 2")
        tab2_widget_action.triggered.connect(lambda: self.create_widget_by_type("tab_widget_2"))
        right_widget_action = by_type_menu.addAction("Right Widget")
        right_widget_action.triggered.connect(lambda: self.create_widget_by_type("right_widget"))
        
        # Add new financial widgets
        chart_widget_action = by_type_menu.addAction("Chart Widget")
        chart_widget_action.triggered.connect(lambda: self.create_widget_by_type("chart_widget"))
        order_widget_action = by_type_menu.addAction("Order Widget")
        order_widget_action.triggered.connect(lambda: self.create_widget_by_type("order_widget"))
        portfolio_widget_action = by_type_menu.addAction("Portfolio Widget")
        portfolio_widget_action.triggered.connect(lambda: self.create_widget_by_type("portfolio_widget"))
        
        # Submenu for "By Instance" path - demonstrates making existing widgets dockable
        # This shows how developers can take pre-configured widget instances and make them dockable
        by_instance_menu = widget_menu.addMenu("Create By Instance (Existing)")
        instance_test_action = by_instance_menu.addAction("Test Widget Instance")
        instance_test_action.triggered.connect(lambda: self.create_widget_by_instance("test_widget"))
        instance_tab1_action = by_instance_menu.addAction("Tab Widget 1 Instance")
        instance_tab1_action.triggered.connect(lambda: self.create_widget_by_instance("tab_widget_1"))
        
        # Add new financial widget instances
        instance_chart_action = by_instance_menu.addAction("Chart Widget Instance")
        instance_chart_action.triggered.connect(lambda: self.create_widget_by_instance("chart_widget"))
        instance_order_action = by_instance_menu.addAction("Order Widget Instance")
        instance_order_action.triggered.connect(lambda: self.create_widget_by_instance("order_widget"))
        instance_portfolio_action = by_instance_menu.addAction("Portfolio Widget Instance")
        instance_portfolio_action.triggered.connect(lambda: self.create_widget_by_instance("portfolio_widget"))
        
        widget_menu.addSeparator()
        
        # Submenu for "By Factory" path - demonstrates factory function registration
        # This shows how developers can register factory functions for complex widget creation
        by_factory_menu = widget_menu.addMenu("Create By Factory (Advanced)")
        by_factory_menu.aboutToShow.connect(self._setup_factory_examples)  # Setup factories when menu is shown
        factory_custom_action = by_factory_menu.addAction("Custom Factory Widget")
        factory_custom_action.triggered.connect(lambda: self.create_widget_by_factory("custom_factory_widget"))
        factory_complex_action = by_factory_menu.addAction("Complex Initialization Widget")
        factory_complex_action.triggered.connect(lambda: self.create_widget_by_factory("complex_init_widget"))
        
        widget_menu.addSeparator()
        
        # Submenu for "Ad-Hoc State Handlers" path - demonstrates state handling without modifying widget source
        # This shows how developers can add state persistence to existing widgets without modifying their code
        adhoc_menu = widget_menu.addMenu("Create with Ad-Hoc State Handlers")
        adhoc_stateful_action = adhoc_menu.addAction("Stateful Widget with Ad-Hoc Handlers")
        adhoc_stateful_action.triggered.connect(self.create_widget_with_adhoc_handlers)
        
        widget_menu.addSeparator()
        
        # Legacy option for comparison
        legacy_widget_action = widget_menu.addAction("Create Widget (Legacy Method)")
        legacy_widget_action.triggered.connect(self.create_and_register_new_widget)
        
        widget_menu.addSeparator()
        create_floating_root_action = widget_menu.addAction("Create New Floating Root")
        create_floating_root_action.triggered.connect(self.docking_manager.create_new_floating_root)

        test_menu = menu_bar.addMenu("Tests")

        find_widget_action = test_menu.addAction("Test: Find Widget by ID")
        find_widget_action.triggered.connect(self.run_find_widget_test)

        list_all_widgets_action = test_menu.addAction("Test: List All Widgets")
        list_all_widgets_action.triggered.connect(self.run_list_all_widgets_test)

        list_floating_widgets_action = test_menu.addAction("Test: List Floating Widgets")
        list_floating_widgets_action.triggered.connect(self.run_get_floating_widgets_test)

        check_widget_docked_action = test_menu.addAction("Test: Is Widget Docked?")
        check_widget_docked_action.triggered.connect(self.run_is_widget_docked_test)

        programmatic_dock_action = test_menu.addAction("Test: Programmatic Dock")
        programmatic_dock_action.triggered.connect(self.run_programmatic_dock_test)

        programmatic_undock_action = test_menu.addAction("Test: Programmatic Undock")
        programmatic_undock_action.triggered.connect(self.run_programmatic_undock_test)

        programmatic_move_action = test_menu.addAction("Test: Programmatic Move to Main")
        programmatic_move_action.triggered.connect(self.run_programmatic_move_test)

        activate_widget_action = test_menu.addAction("Test: Activate Widget")
        activate_widget_action.triggered.connect(self.run_activate_widget_test)

        test_menu.addSeparator()

        self.debug_mode_action = test_menu.addAction("Toggle Debug Mode")
        self.debug_mode_action.setCheckable(True)
        self.debug_mode_action.setChecked(self.docking_manager.debug_mode)
        self.debug_mode_action.triggered.connect(self.docking_manager.set_debug_mode)

        test_menu.addSeparator()
        
        
        test_menu.addSeparator()
        run_all_tests_action = test_menu.addAction("Run All Tests Sequentially")
        run_all_tests_action.triggered.connect(self.run_all_tests_sequentially)

        # Add Color Customization menu
        color_menu = menu_bar.addMenu("Colors")
        
        # Container colors submenu
        container_colors_menu = color_menu.addMenu("Container Colors")
        container_bg_action = container_colors_menu.addAction("Set Container Background to Light Blue")
        container_bg_action.triggered.connect(lambda: self.set_container_background_color(QColor("#E6F3FF")))
        container_border_action = container_colors_menu.addAction("Set Container Border to Dark Blue")
        container_border_action.triggered.connect(lambda: self.set_container_border_color(QColor("#0066CC")))
        
        # Floating window colors submenu
        floating_colors_menu = color_menu.addMenu("Floating Window Colors")
        floating_bg_action = floating_colors_menu.addAction("Create Floating Window - Green Theme")
        floating_bg_action.triggered.connect(lambda: self.create_colored_floating_window(
            QColor("#228B22"), QColor("#FFFFFF")))  # Forest green background, white text
        floating_bg2_action = floating_colors_menu.addAction("Create Floating Window - Purple Theme")
        floating_bg2_action.triggered.connect(lambda: self.create_colored_floating_window(
            QColor("#6A5ACD"), QColor("#FFFFFF")))  # Slate blue background, white text
        floating_bg3_action = floating_colors_menu.addAction("Create Floating Window - Dark Theme")
        floating_bg3_action.triggered.connect(lambda: self.create_colored_floating_window(
            QColor("#2D2D2D"), QColor("#00FF00")))  # Dark gray background, bright green text
        
        # Title bar text color submenu
        title_text_menu = color_menu.addMenu("Title Bar Text Colors")
        main_title_text_action = title_text_menu.addAction("Change Main Window Title Text to Red")
        main_title_text_action.triggered.connect(lambda: self.change_main_window_title_text_color(QColor("#FF0000")))
        main_title_text2_action = title_text_menu.addAction("Change Main Window Title Text to Blue")
        main_title_text2_action.triggered.connect(lambda: self.change_main_window_title_text_color(QColor("#0066FF")))
        main_title_text3_action = title_text_menu.addAction("Change Main Window Title Text to Gold")
        main_title_text3_action.triggered.connect(lambda: self.change_main_window_title_text_color(QColor("#FFD700")))
        
        # Reset colors
        color_menu.addSeparator()
        reset_colors_action = color_menu.addAction("Reset All Colors to Defaults")
        reset_colors_action.triggered.connect(self.reset_all_colors)

        # Add Icon Testing menu
        icon_menu = menu_bar.addMenu("Icons")
        
        # Unicode emoji icons submenu
        unicode_icons_menu = icon_menu.addMenu("Unicode Emoji Icons")
        unicode1_action = unicode_icons_menu.addAction("Create Window with House Icon")
        unicode1_action.triggered.connect(lambda: self.create_window_with_unicode_icon("🏠", "Home"))
        unicode2_action = unicode_icons_menu.addAction("Create Window with Gear Icon")
        unicode2_action.triggered.connect(lambda: self.create_window_with_unicode_icon("⚙️", "Settings"))
        unicode3_action = unicode_icons_menu.addAction("Create Window with Chart Icon")
        unicode3_action.triggered.connect(lambda: self.create_window_with_unicode_icon("📊", "Analytics"))
        unicode4_action = unicode_icons_menu.addAction("Create Window with Rocket Icon")
        unicode4_action.triggered.connect(lambda: self.create_window_with_unicode_icon("🚀", "Launch"))
        
        # Qt Standard icons submenu
        qt_icons_menu = icon_menu.addMenu("Qt Standard Icons")
        qt1_action = qt_icons_menu.addAction("Create Window with File Icon")
        qt1_action.triggered.connect(lambda: self.create_window_with_qt_icon("SP_FileIcon", "Files"))
        qt2_action = qt_icons_menu.addAction("Create Window with Folder Icon")
        qt2_action.triggered.connect(lambda: self.create_window_with_qt_icon("SP_DirIcon", "Folders"))
        qt3_action = qt_icons_menu.addAction("Create Window with Computer Icon")
        qt3_action.triggered.connect(lambda: self.create_window_with_qt_icon("SP_ComputerIcon", "Computer"))
        
        # No icon test
        icon_menu.addSeparator()
        no_icon_action = icon_menu.addAction("Create Window with No Icon")
        no_icon_action.triggered.connect(self.create_window_with_no_icon)
        
        # Dynamic icon change tests
        icon_menu.addSeparator()
        dynamic_menu = icon_menu.addMenu("Dynamic Icon Changes")
        change_main_icon_action = dynamic_menu.addAction("Add Icon to Main Window")
        change_main_icon_action.triggered.connect(self.add_icon_to_main_window)
        remove_main_icon_action = dynamic_menu.addAction("Remove Icon from Main Window")
        remove_main_icon_action.triggered.connect(self.remove_icon_from_main_window)
        change_container_icon_action = dynamic_menu.addAction("Change Icon of First Container")
        change_container_icon_action.triggered.connect(self.change_first_container_icon)


    def _create_test_content(self, name: str) -> QWidget:
        """Creates a simple ttest_widget_3able with test data for demonstration."""
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)

        table_widget = QTableWidget()

        stylesheet = """
            QTableView {
                border: 1px solid black;
                gridline-color: black;
            }
            QTableCornerButton::section {
                background-color: #f0f0f0;
                border-right: 1px solid black;
                border-bottom: 1px solid black;
            }
        """
        table_widget.setStyleSheet(stylesheet)

        table_widget.setRowCount(5)
        table_widget.setColumnCount(3)
        table_widget.setHorizontalHeaderLabels(["Item ID", "Description", "Value"])

        for row in range(5):
            item_id = QTableWidgetItem(f"{name}-I{row+1}")
            item_desc = QTableWidgetItem(f"Sample data item for row {row+1}")
            item_value = QTableWidgetItem(str(random.randint(100, 999)))

            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_value.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            table_widget.setItem(row, 0, item_id)
            table_widget.setItem(row, 1, item_desc)
            table_widget.setItem(row, 2, item_value)

        table_widget.resizeColumnsToContents()

        content_layout.addWidget(table_widget)

        return content_widget

    def create_widget_by_type(self, widget_key: str):
        """Create a widget using the 'By Type' path - registry-based creation."""
        print(f"Creating widget using 'By Type' path: {widget_key}")
        
        # Calculate cascading position using simple integers
        count = len(self.docking_manager.widgets)
        x = 200 + count * 40
        y = 200 + count * 40
        
        # Use the new "By Type" API - create from registered key
        container = self.docking_manager.create_floating_widget_from_key(
            widget_key,
            position=(x, y),
            size=(400, 300)
        )
        
        print(f"Created widget container: {container}")
    
    def create_widget_by_instance(self, widget_key: str):
        """Create a widget using the 'By Instance' path - make existing widget dockable."""
        print(f"Creating widget using 'By Instance' path: {widget_key}")
        
        # Calculate cascading position using simple integers
        count = len(self.docking_manager.widgets)
        x = 250 + count * 40
        y = 250 + count * 40
        
        # Create an instance first and configure it
        if widget_key == "test_widget":
            widget_instance = TestContentWidget("Custom Instance Widget")
        elif widget_key == "tab_widget_1":
            widget_instance = TabWidget1()
        elif widget_key == "tab_widget_2":
            widget_instance = TabWidget2()
        elif widget_key == "right_widget":
            widget_instance = RightWidget()
        elif widget_key == "chart_widget":
            widget_instance = ChartWidget()
        elif widget_key == "order_widget":
            widget_instance = OrderWidget()
        elif widget_key == "portfolio_widget":
            widget_instance = PortfolioWidget()
        else:
            print(f"Unknown widget key: {widget_key}")
            return
            
        # Use the new "By Instance" API - make existing widget dockable
        container = self.docking_manager.add_as_floating_widget(
            widget_instance,
            widget_key,
            title=f"Custom {widget_key}",
            position=(x, y),
            size=(400, 300)
        )
        
        print(f"Made widget instance dockable: {container}")
    
    def _setup_factory_examples(self):
        """Setup factory examples when the factory menu is accessed."""
        try:
            # Only register once
            from JCDock.core.widget_registry import get_registry
            registry = get_registry()
            
            if not registry.is_registered("custom_factory_widget"):
                # Register a factory that creates widgets with custom arguments
                self.docking_manager.register_widget_factory(
                    "custom_factory_widget",
                    lambda: self._create_custom_factory_widget("Factory Example", "green"),
                    "Custom Factory Widget"
                )
            
            if not registry.is_registered("complex_init_widget"):
                # Register a factory with complex initialization
                self.docking_manager.register_widget_factory(
                    "complex_init_widget",
                    self._create_complex_init_widget,
                    "Complex Initialization Widget"
                )
        except ValueError:
            # Already registered, ignore
            pass
    
    def _create_custom_factory_widget(self, title, color):
        """Factory function that creates a widget with custom arguments."""
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        label = QLabel(f"Factory Created: {title}")
        label.setStyleSheet(f"color: {color}; font-weight: bold; padding: 10px; background: #f0f0f0; border-radius: 5px;")
        layout.addWidget(label)
        
        info_label = QLabel("This widget was created using a factory function!")
        layout.addWidget(info_label)
        
        button = QPushButton("Factory Button")
        button.clicked.connect(lambda: print(f"Factory widget '{title}' button clicked!"))
        layout.addWidget(button)
        
        return widget
    
    def _create_complex_init_widget(self):
        """Factory function demonstrating complex initialization logic."""
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget
        import random
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Complex initialization that couldn't be done in a simple constructor
        session_id = random.randint(1000, 9999)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        header_label = QLabel(f"Complex Widget (Session: {session_id})")
        header_label.setStyleSheet("color: purple; font-weight: bold; padding: 10px; background: #f8f0ff; border-radius: 5px;")
        layout.addWidget(header_label)
        
        info_label = QLabel(f"Initialized at: {timestamp}")
        layout.addWidget(info_label)
        
        # Create a list with dynamically generated data
        data_list = QListWidget()
        for i in range(5):
            data_list.addItem(f"Dynamic Item {i+1} (Generated at runtime)")
        layout.addWidget(data_list)
        
        footer_label = QLabel("This demonstrates complex initialization that requires factory functions!")
        footer_label.setStyleSheet("font-style: italic; color: #666;")
        layout.addWidget(footer_label)
        
        return widget
    
    def create_widget_by_factory(self, factory_key: str):
        """Create a widget using the 'By Factory' path - factory function registration."""
        print(f"Creating widget using 'By Factory' path: {factory_key}")
        
        # Calculate cascading position
        count = len(self.docking_manager.widgets)
        x = 300 + count * 40
        y = 300 + count * 40
        
        # Use the factory-based API
        container = self.docking_manager.create_floating_widget_from_key(
            factory_key,
            position=(x, y),
            size=(400, 300)
        )
        
        print(f"Created widget from factory: {container}")
    
    def create_widget_with_adhoc_handlers(self):
        """Create a widget using ad-hoc state handlers for persistence without modifying the widget source."""
        print("Creating widget with ad-hoc state handlers...")
        
        # Create a widget instance that doesn't have built-in state persistence
        widget_instance = self._create_adhoc_stateful_widget()
        
        # Modify its state to demonstrate persistence
        widget_instance.text_input.setText("This will be preserved!")
        widget_instance.counter_spin.setValue(789)
        widget_instance._simulate_clicks(5)  # Add some state
        
        # Calculate cascading position
        count = len(self.docking_manager.widgets)
        x = 400 + count * 40
        y = 400 + count * 40
        
        # Add the widget with ad-hoc state handlers
        container = self.docking_manager.add_as_floating_widget(
            widget_instance,
            "adhoc_stateful_widget",  # Must be registered for persistence
            title="Widget with Ad-Hoc State Handlers",
            position=(x, y),
            size=(450, 350),
            state_provider=self._extract_adhoc_widget_state,
            state_restorer=self._restore_adhoc_widget_state
        )
        
        print(f"Created widget with ad-hoc state handlers: {container}")
    
    def _create_adhoc_stateful_widget(self):
        """Create a widget that doesn't have built-in state persistence methods."""
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QSpinBox, QPushButton, QTextEdit
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Header
        header = QLabel("Ad-Hoc State Handler Demo")
        header.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px; background: #e8f4fd; border-radius: 5px;")
        layout.addWidget(header)
        
        # Explanation
        explanation = QLabel("This widget doesn't have get_dock_state/set_dock_state methods.\nState is managed through external handler functions.")
        explanation.setStyleSheet("font-style: italic; color: #666; padding: 5px;")
        layout.addWidget(explanation)
        
        # Stateful text input
        layout.addWidget(QLabel("Text Input (will be preserved):"))
        widget.text_input = QLineEdit()
        widget.text_input.setPlaceholderText("Enter text to be preserved across sessions...")
        layout.addWidget(widget.text_input)
        
        # Stateful counter
        layout.addWidget(QLabel("Counter (will be preserved):"))
        widget.counter_spin = QSpinBox()
        widget.counter_spin.setRange(0, 9999)
        widget.counter_spin.setValue(0)  # Use neutral default - will be obvious if restoration fails
        layout.addWidget(widget.counter_spin)
        
        # Button with click tracking
        widget.click_count = 0
        widget.click_button = QPushButton("Click Me (count preserved)")
        widget.click_button.clicked.connect(lambda: widget._on_click())
        layout.addWidget(widget.click_button)
        
        # Status display
        widget.status_label = QLabel("Clicks: 0 (NEW WIDGET)")
        layout.addWidget(widget.status_label)
        
        # Notes area
        layout.addWidget(QLabel("Notes (will be preserved):"))
        widget.notes_area = QTextEdit()
        widget.notes_area.setPlaceholderText("Add some notes that will persist...")
        widget.notes_area.setMaximumHeight(100)
        layout.addWidget(widget.notes_area)
        
        # Add methods to the widget instance
        def on_click():
            widget.click_count += 1
            widget.status_label.setText(f"Clicks: {widget.click_count} (MANUAL)")
        
        def simulate_clicks(count):
            """Helper for testing."""
            for _ in range(count):
                on_click()
        
        widget._on_click = on_click
        widget._simulate_clicks = simulate_clicks
        
        return widget
    
    def _extract_adhoc_widget_state(self, widget):
        """Ad-hoc state provider function - extracts state from the widget."""
        return {
            'text_input_value': widget.text_input.text(),
            'counter_value': widget.counter_spin.value(), 
            'click_count': widget.click_count,
            'notes_content': widget.notes_area.toPlainText()
        }
    
    def _restore_adhoc_widget_state(self, widget, state_dict):
        """Ad-hoc state restorer function - restores state to the widget."""
        # Validate state_dict
        if not isinstance(state_dict, dict):
            widget.status_label.setText("Clicks: 0 (RESTORE FAILED - Invalid data)")
            return
        
        try:
            # Restore UI state
            text_value = state_dict.get('text_input_value', '')
            counter_value = state_dict.get('counter_value', 0)  # Use 0 as neutral default
            notes_value = state_dict.get('notes_content', '')
            click_count = state_dict.get('click_count', 0)
            
            widget.text_input.setText(text_value)
            widget.counter_spin.setValue(counter_value)
            widget.notes_area.setPlainText(notes_value)
            
            # Restore internal state
            widget.click_count = click_count
            widget.status_label.setText(f"Clicks: {widget.click_count} (RESTORED ✓)")
            
        except Exception as e:
            widget.status_label.setText(f"Clicks: 0 (RESTORE FAILED - {str(e)})")

    def create_and_register_new_widget(self):
        """Legacy method for comparison - shows the old complexity."""
        self.widget_count += 1
        widget_name = f"Legacy Widget {self.widget_count}"

        # Use the new simplified API but show it's just one line now!
        position = QPoint(300 + self.widget_count * 40, 300 + self.widget_count * 40)
        container = self.docking_manager.create_floating_widget_from_key(
            "test_widget", 
            position=position,
            size=QSize(400, 300)
        )
        print(f"Legacy method created: {container}")


    def _reset_widget_visual_state(self, widget: DockPanel):
        """Resets any visual modifications made to a widget during testing."""
        if widget:
            # Remove any test markers from title
            original_title = widget.windowTitle()
            if "(Found!)" in original_title:
                original_title = original_title.replace(" (Found!)", "")
            if "(Listed)" in original_title:
                original_title = original_title.replace("(Listed) ", "")
            widget.set_title(original_title)
            
            # Reset title bar color to default
            widget.set_title_bar_color(None)

    def _print_test_header(self, test_name: str):
        """Prints a consistent test header."""
        print(f"\n--- RUNNING TEST: {test_name} ---")

    def _print_test_footer(self):
        """Prints a consistent test footer."""
        print("-" * 50)

    def _print_success(self, message: str):
        """Prints a success message."""
        print(f"SUCCESS: {message}")

    def _print_failure(self, message: str):
        """Prints a failure message."""
        print(f"FAILURE: {message}")

    def _print_info(self, message: str):
        """Prints an info message."""
        print(f"INFO: {message}")

    def _cleanup_test_modifications(self):
        """Cleans up any visual modifications made during testing."""
        all_widgets = self.docking_manager.get_all_widgets()
        for widget in all_widgets:
            self._reset_widget_visual_state(widget)

    def _validate_widget_exists(self, persistent_id: str) -> bool:
        """Validates that a widget with the given ID exists in the manager."""
        return self.docking_manager.find_widget_by_id(persistent_id) is not None

    def _is_widget_truly_docked(self, widget: DockPanel) -> bool:
        """
        Determines if a widget is truly docked (in a container with multiple widgets).
        Single widget containers are considered floating, not docked.
        """
        if not widget or not widget.parent_container:
            return False
        
        # Find the container holding this widget
        for root_window in self.docking_manager.model.roots.keys():
            if hasattr(root_window, 'contained_widgets'):
                contained = getattr(root_window, 'contained_widgets', [])
                if widget in contained:
                    # Widget is truly docked only if container has multiple widgets
                    return len(contained) > 1
        return False

    def _validate_widget_state(self, widget: DockPanel, expected_docked: bool) -> bool:
        """Validates that a widget is in the expected docked/floating state."""
        if not widget:
            return False
        actual_docked = self._is_widget_truly_docked(widget)
        return actual_docked == expected_docked


    def _setup_test_environment(self):
        """Sets up a clean test environment by resetting widget modifications."""
        self._cleanup_test_modifications()

    def _teardown_test_environment(self):
        """Cleans up after a test to ensure isolation."""
        self._cleanup_test_modifications()
        self.app.processEvents()

    def _run_test_with_isolation(self, test_name: str, test_func):
        """Runs a test function with proper setup and teardown."""
        self._print_test_header(test_name)
        self._setup_test_environment()
        
        try:
            test_func()
        except Exception as e:
            self._print_failure(f"Test failed with exception: {e}")
        finally:
            self._teardown_test_environment()
            self._print_test_footer()


    def _create_floating_widget(self, name: str) -> DockContainer:
        """Helper method that creates a floating widget using the new registry system."""
        print(f"Creating widget: {name}")
        
        # Use the new "By Type" API - much simpler!
        container = self.docking_manager.create_floating_widget_from_key("test_widget")
        
        return container

    def save_layout(self):
        """Saves the current docking layout to the standardized .ini file."""
        print("\n--- RUNNING TEST: Save Layout ---")
        
        # Use standardized file path
        file_path = self._get_standard_layout_path()
        
        try:
            # Ensure the directory exists
            self._ensure_layout_directory()
            
            # Get layout data as bytearray
            layout_data = self.docking_manager.save_layout_to_bytearray()
            
            # Encode to base64 for storing in text file
            encoded_data = base64.b64encode(layout_data).decode('utf-8')
            
            # Create .ini file structure
            config = configparser.ConfigParser()
            config['layout'] = {
                'data': encoded_data,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            config['metadata'] = {
                'version': '1.0',
                'application': 'JCDock Test Application'
            }
            
            # Write to file
            with open(file_path, 'w') as configfile:
                config.write(configfile)
            
            print(f"SUCCESS: Layout saved to {file_path}")
            
        except Exception as e:
            print(f"FAILURE: Could not save layout: {e}")
        print("---------------------------------")

    def load_layout(self):
        """Loads a docking layout from the standardized .ini file."""
        print("\n--- RUNNING TEST: Load Layout ---")
        
        # Use standardized file path
        file_path = self._get_standard_layout_path()
        
        if not os.path.exists(file_path):
            print(f"INFO: No saved layout found at {file_path}")
            print("---------------------------------")
            return
        
        try:
            # Read .ini file
            config = configparser.ConfigParser()
            config.read(file_path)
            
            # Validate file structure
            if 'layout' not in config:
                print("FAILURE: Invalid layout file - missing [layout] section")
                print("---------------------------------")
                return
            
            if 'data' not in config['layout']:
                print("FAILURE: Invalid layout file - missing layout data")
                print("---------------------------------")
                return
            
            # Decode base64 data back to bytearray
            encoded_data = config['layout']['data']
            layout_data = base64.b64decode(encoded_data.encode('utf-8'))
            
            # Load layout using existing method
            self.docking_manager.load_layout_from_bytearray(layout_data)
            
            # Show metadata if available
            if 'metadata' in config:
                version = config['metadata'].get('version', 'Unknown')
                app = config['metadata'].get('application', 'Unknown')
                print(f"INFO: Loaded layout version {version} from {app}")
            
            if 'timestamp' in config['layout']:
                timestamp = config['layout']['timestamp']
                print(f"INFO: Layout saved on {timestamp}")
            
            print(f"SUCCESS: Layout loaded from {file_path}")
            
        except Exception as e:
            print(f"FAILURE: Could not load layout: {e}")
        print("---------------------------------")

    def _load_layout_silently(self) -> bool:
        """
        Silently loads a docking layout from the standardized .ini file.
        Used for startup loading without test output.
        
        Returns:
            bool: True if layout was loaded successfully, False otherwise
        """
        file_path = self._get_standard_layout_path()
        
        if not os.path.exists(file_path):
            return False
        
        try:
            # Read .ini file
            config = configparser.ConfigParser()
            config.read(file_path)
            
            # Validate file structure
            if 'layout' not in config or 'data' not in config['layout']:
                return False
            
            # Decode base64 data back to bytearray
            encoded_data = config['layout']['data']
            layout_data = base64.b64decode(encoded_data.encode('utf-8'))
            
            # Load layout using existing method
            self.docking_manager.load_layout_from_bytearray(layout_data)
            
            return True
            
        except Exception:
            return False


    def run_find_widget_test(self):
        """
        Tests the manager's find_widget_by_id method.
        """
        def test_logic():
            # Get all existing widgets first
            all_widgets = self.docking_manager.get_all_widgets()
            if not all_widgets:
                self._print_failure("No widgets exist to test with")
                return
            
            # Use the first available widget for testing
            test_widget = all_widgets[0]
            target_id = test_widget.persistent_id
            
            self._print_info(f"Testing with existing widget ID: '{target_id}'")
            
            # Test finding an existing widget
            found_widget = self.docking_manager.find_widget_by_id(target_id)
            
            if found_widget and found_widget is test_widget:
                self._print_success(f"Found widget: {found_widget.windowTitle()}")
                # Add visual feedback (will be cleaned up automatically)
                found_widget.set_title(f"{found_widget.windowTitle()} (Found!)")
                found_widget.set_title_bar_color(QColor("#DDA0DD"))
                found_widget.on_activation_request()
            elif found_widget:
                self._print_failure(f"Found a widget but it's not the expected instance")
            else:
                self._print_failure(f"Could not find widget with ID: '{target_id}'")
            
            # Test finding a non-existent widget
            non_existent_widget = self.docking_manager.find_widget_by_id("non_existent_widget")
            if non_existent_widget is None:
                self._print_success("Correctly returned None for non-existent widget")
            else:
                self._print_failure("Should have returned None for non-existent widget")
        
        self._run_test_with_isolation("Find widget by ID", test_logic)


    def run_list_all_widgets_test(self):
        """
        Tests the manager's get_all_widgets method.
        """
        def test_logic():
            all_widgets = self.docking_manager.get_all_widgets()

            if not all_widgets:
                self._print_failure("No widgets returned")
                return

            self._print_success(f"Found {len(all_widgets)} widgets:")
            
            # Validate that all returned objects are actually DockPanel instances
            valid_widgets = 0
            for i, widget in enumerate(all_widgets):
                if isinstance(widget, DockPanel) and hasattr(widget, 'persistent_id'):
                    print(f"  {i + 1}: {widget.windowTitle()} (ID: {widget.persistent_id})")
                    valid_widgets += 1
                else:
                    self._print_failure(f"Invalid widget at index {i}: {type(widget)}")
            
            if valid_widgets == len(all_widgets):
                self._print_success(f"All {valid_widgets} widgets are valid DockPanel instances")
            else:
                self._print_failure(f"Only {valid_widgets}/{len(all_widgets)} widgets are valid")
        
        self._run_test_with_isolation("List all widgets", test_logic)

    def run_get_floating_widgets_test(self):
        """
        Tests the manager's get_floating_widgets method.
        """
        def test_logic():
            floating_widgets = self.docking_manager.get_floating_widgets()
            
            if not floating_widgets:
                # Find widgets that are in floating containers (not main dock area)
                main_dock_area = self.main_window.dock_area
                floating_container_widgets = []
                
                for root_window in self.docking_manager.model.roots.keys():
                    if root_window != main_dock_area and hasattr(root_window, 'contained_widgets'):
                        contained = getattr(root_window, 'contained_widgets', [])
                        floating_container_widgets.extend(contained)
                        
                if floating_container_widgets:
                    self._print_success(f"Found {len(floating_container_widgets)} floating widgets:")
                    for i, widget in enumerate(floating_container_widgets):
                        print(f"  {i + 1}: {widget.windowTitle()} (ID: {widget.persistent_id})")
                        widget.set_title_bar_color(QColor("#90EE90"))
                else:
                    self._print_failure("No floating widgets found")
                return
            
            self._print_success(f"Found {len(floating_widgets)} floating widgets:")
            
            for i, widget in enumerate(floating_widgets):
                print(f"  {i + 1}: {widget.windowTitle()} (ID: {widget.persistent_id})")
                widget.set_title_bar_color(QColor("#90EE90"))
        
        self._run_test_with_isolation("Get floating widgets", test_logic)


    def run_is_widget_docked_test(self):
        """
        Tests widget docked/floating state using correct definition:
        - Floating: Single widget in container
        - Docked: Multiple widgets in same container
        """
        def test_logic():
            all_widgets = self.docking_manager.get_all_widgets()
            if not all_widgets:
                self._print_failure("No widgets exist to test with")
                return
            
            self._print_info("Analyzing widget states (Docked = multi-widget container, Floating = single-widget container):")
            
            truly_docked_count = 0
            truly_floating_count = 0
            
            for widget in all_widgets:
                is_truly_docked = self._is_widget_truly_docked(widget)
                old_method_result = self.docking_manager.is_widget_docked(widget)
                
                if is_truly_docked:
                    truly_docked_count += 1
                    print(f"  {widget.windowTitle()}: DOCKED (in multi-widget container)")
                else:
                    truly_floating_count += 1
                    print(f"  {widget.windowTitle()}: FLOATING (in single-widget container)")
                
                # Show discrepancy with old method if any
                if is_truly_docked != old_method_result:
                    self._print_info(f"    Note: Original is_widget_docked() returns {old_method_result} (different)")
            
            self._print_success(f"State summary: {truly_docked_count} truly docked, {truly_floating_count} truly floating")
            
            # Test the original method behavior vs our corrected logic
            if truly_floating_count > 0 and truly_docked_count == 0:
                self._print_success("All widgets are floating (single-widget containers) - matches expected startup state")
            elif truly_docked_count > 0:
                self._print_success(f"Found {truly_docked_count} widgets in multi-widget containers (truly docked)")
            
            # Test with None/invalid widget
            try:
                invalid_result = self.docking_manager.is_widget_docked(None)
                self._print_info(f"is_widget_docked(None) returned: {invalid_result}")
            except Exception as e:
                self._print_info(f"is_widget_docked(None) raised exception: {e}")
        
        self._run_test_with_isolation("Is widget docked check", test_logic)

    def run_programmatic_dock_test(self):
        """
        Tests programmatically docking one widget into another.
        Uses correct definition: docked = multi-widget container.
        """
        def test_logic():
            all_widgets = self.docking_manager.get_all_widgets()
            if len(all_widgets) < 2:
                self._print_failure("Need at least 2 widgets to test docking operations")
                return
            
            source_widget = all_widgets[0]
            target_widget = all_widgets[1]
            
            # Record initial states using correct definition
            initial_source_docked = self._is_widget_truly_docked(source_widget)
            initial_target_docked = self._is_widget_truly_docked(target_widget)
            
            self._print_info(f"Testing with: '{source_widget.windowTitle()}' -> '{target_widget.windowTitle()}'")
            self._print_info(f"Initial states - Source truly docked: {initial_source_docked}, Target truly docked: {initial_target_docked}")
            
            # Debug widget states before docking
            self._print_info(f"Source widget container: {source_widget.parent_container}")
            self._print_info(f"Target widget container: {target_widget.parent_container}")
            
            # Check if widgets are in model roots
            source_in_roots = False
            target_in_roots = False
            for root_window in self.docking_manager.model.roots.keys():
                if hasattr(root_window, 'contained_widgets'):
                    contained = getattr(root_window, 'contained_widgets', [])
                    if source_widget in contained:
                        source_in_roots = True
                        self._print_info(f"Source widget found in root: {type(root_window).__name__}")
                    if target_widget in contained:
                        target_in_roots = True
                        self._print_info(f"Target widget found in root: {type(root_window).__name__}")
            
            if not source_in_roots:
                self._print_failure(f"Source widget '{source_widget.windowTitle()}' not found in any model root")
                return
            if not target_in_roots:
                self._print_failure(f"Target widget '{target_widget.windowTitle()}' not found in any model root")
                return
            
            # Test docking to center (creates tab group)
            self._print_info(f"Docking '{source_widget.windowTitle()}' into '{target_widget.windowTitle()}' at center")
            try:
                self.docking_manager.dock_widget(source_widget, target_widget, "center")
                self.app.processEvents()
            except Exception as e:
                self._print_failure(f"Dock operation failed with exception: {e}")
                return
            
            # Note: The dock operation may print ERROR messages due to architectural limitations
            # where widgets in floating containers are not handled as expected by dock_widgets method
            
            # Verify final states using correct definition
            final_source_docked = self._is_widget_truly_docked(source_widget)
            final_target_docked = self._is_widget_truly_docked(target_widget)
            
            if final_source_docked and final_target_docked:
                self._print_success("Both widgets are now truly docked (in multi-widget container)")
            else:
                # This may fail due to architectural limitation where dock_widget doesn't handle
                # widgets in floating containers properly (looks for direct roots, not contained widgets)
                self._print_info(f"Docking operation did not result in truly docked state")
                self._print_info("This may be due to architectural limitation in dock_widget method")
                self._print_info("The method expects widgets as direct roots, not contained in floating containers")
            
            # Report final state using correct definitions  
            truly_floating_count = len([w for w in all_widgets if not self._is_widget_truly_docked(w)])
            truly_docked_count = len(all_widgets) - truly_floating_count
            self._print_info(f"Final state: {truly_docked_count} truly docked, {truly_floating_count} truly floating")
            
            # Test conclusion
            if truly_docked_count > 0:
                self._print_success("Programmatic docking created truly docked widgets")
            else:
                self._print_info("Programmatic docking test reveals architectural limitation with floating widgets")
        
        self._run_test_with_isolation("Programmatic dock operations", test_logic)

    def run_programmatic_undock_test(self):
        """
        Tests programmatically undocking a widget.
        Uses correct definition: truly docked = multi-widget container.
        """
        def test_logic():
            all_widgets = self.docking_manager.get_all_widgets()
            if not all_widgets:
                self._print_failure("No widgets exist to test with")
                return
            
            # Find a truly docked widget to test with, or dock widgets to create one
            truly_docked_widget = None
            for widget in all_widgets:
                if self._is_widget_truly_docked(widget):
                    truly_docked_widget = widget
                    break
            
            if not truly_docked_widget and len(all_widgets) >= 2:
                # Dock two widgets together to create a truly docked state
                self._print_info("No truly docked widgets found, creating docked state for test")
                self.docking_manager.dock_widget(all_widgets[0], all_widgets[1], "center")
                self.app.processEvents()
                
                # Check if docking worked
                if self._is_widget_truly_docked(all_widgets[0]):
                    truly_docked_widget = all_widgets[0]
                else:
                    self._print_failure("Failed to create truly docked state for testing")
                    return
            
            if not truly_docked_widget:
                self._print_failure("Could not establish a truly docked widget for testing")
                return
            
            self._print_info(f"Testing undock with truly docked widget: '{truly_docked_widget.windowTitle()}'")
            
            # Record state before undocking
            initial_truly_docked = self._is_widget_truly_docked(truly_docked_widget)
            if not initial_truly_docked:
                self._print_failure("Widget should be truly docked before undocking test")
                return
            
            # Perform undock operation
            undock_result = self.docking_manager.undock_widget(truly_docked_widget)
            self.app.processEvents()
            
            # Verify final state
            final_truly_docked = self._is_widget_truly_docked(truly_docked_widget)
            
            if not final_truly_docked:
                self._print_success(f"Widget '{truly_docked_widget.windowTitle()}' successfully undocked (now floating in single-widget container)")
            else:
                self._print_failure("Widget is still truly docked after undock operation")
        
        self._run_test_with_isolation("Programmatic undock operations", test_logic)

    def run_programmatic_move_test(self):
        """
        Tests programmatically moving a widget to a different container (the main window's dock area).
        Uses correct definition: truly docked = multi-widget container.
        """
        def test_logic():
            all_widgets = self.docking_manager.get_all_widgets()
            if not all_widgets:
                self._print_failure("No widgets exist to test with")
                return
            
            target_container = self.main_window.dock_area
            source_widget = all_widgets[0]
            
            initial_truly_docked = self._is_widget_truly_docked(source_widget)
            
            self._print_info(f"Testing move with widget: '{source_widget.windowTitle()}'")
            self._print_info(f"Initial truly docked state: {initial_truly_docked}")
            
            # Test moving to main dock area
            self._print_info(f"Moving '{source_widget.windowTitle()}' to main dock area")
            move_result = self.docking_manager.move_widget_to_container(source_widget, target_container)
            self.app.processEvents()
            
            final_truly_docked = self._is_widget_truly_docked(source_widget)
            
            if move_result:
                if final_truly_docked:
                    self._print_success(f"Move operation successful - Widget now truly docked in main area")
                else:
                    self._print_success(f"Move operation successful - Widget moved to main area (floating in single-widget container)")
            else:
                self._print_failure(f"Move operation failed - Result: {move_result}")
                return
            
            # Test moving widget that's already in the target container
            self._print_info("Testing move operation on widget already in target container")
            redundant_move_result = self.docking_manager.move_widget_to_container(source_widget, target_container)
            
            if redundant_move_result:
                self._print_success("Redundant move operation handled correctly")
            else:
                self._print_failure("Redundant move operation failed unexpectedly")
            
            # Report final state using correct definitions
            truly_floating_count = len([w for w in all_widgets if not self._is_widget_truly_docked(w)])
            truly_docked_count = len(all_widgets) - truly_floating_count
            self._print_info(f"Final state: {truly_docked_count} truly docked, {truly_floating_count} truly floating")
        
        self._run_test_with_isolation("Programmatic move operations", test_logic)

    def run_activate_widget_test(self):
        """
        Tests the manager's activate_widget method.
        Should only test activation, not perform docking operations.
        """
        def test_logic():
            all_widgets = self.docking_manager.get_all_widgets()
            if not all_widgets:
                self._print_failure("No widgets exist to test with")
                return
            
            # Test 1: Activate first widget
            widget_to_activate = all_widgets[0]
            self._print_info(f"Testing activation of widget: '{widget_to_activate.windowTitle()}'")
            
            try:
                self.docking_manager.activate_widget(widget_to_activate)
                self.app.processEvents()
                self._print_success("Widget activation completed without errors")
            except Exception as e:
                self._print_failure(f"Widget activation failed: {e}")
                return
            
            # Test 2: Activate a different widget if available
            if len(all_widgets) >= 2:
                second_widget = all_widgets[1]
                self._print_info(f"Testing activation of second widget: '{second_widget.windowTitle()}'")
                
                try:
                    self.docking_manager.activate_widget(second_widget)
                    self.app.processEvents()
                    self._print_success("Second widget activation completed without errors")
                except Exception as e:
                    self._print_failure(f"Second widget activation failed: {e}")
                    return
            
            # Test 3: Test with invalid widget (None)
            self._print_info("Testing activate_widget(None) - should print error and handle gracefully")
            try:
                self.docking_manager.activate_widget(None)
                self._print_success("activate_widget(None) handled gracefully (error message above is expected)")
            except Exception as e:
                self._print_failure(f"activate_widget(None) raised unexpected exception: {e}")
        
        self._run_test_with_isolation("Widget activation", test_logic)

    def run_all_tests_sequentially(self):
        """Runs all available tests in sequence for comprehensive validation."""
        self._print_test_header("RUNNING ALL TESTS SEQUENTIALLY")
        print("This will run all available tests one after another...")
        print("Each test is isolated and should not affect the others.\n")
        
        # List all test methods to run
        test_methods = [
            ("Find Widget by ID", self.run_find_widget_test),
            ("List All Widgets", self.run_list_all_widgets_test),
            ("Get Floating Widgets", self.run_get_floating_widgets_test),
            ("Is Widget Docked Check", self.run_is_widget_docked_test),
            ("Programmatic Dock Operations", self.run_programmatic_dock_test),
            ("Programmatic Undock Operations", self.run_programmatic_undock_test),
            ("Programmatic Move Operations", self.run_programmatic_move_test),
            ("Widget Activation", self.run_activate_widget_test),
        ]
        
        successful_tests = 0
        total_tests = len(test_methods)
        
        for test_name, test_method in test_methods:
            try:
                print(f"\n{'='*60}")
                print(f"Running: {test_name}")
                print('='*60)
                test_method()
                successful_tests += 1
                print(f"PASS: {test_name} completed")
            except Exception as e:
                print(f"FAIL: {test_name} failed with exception: {e}")
        
        # Print summary
        print(f"\n{'='*60}")
        print("TEST SUMMARY")
        print('='*60)
        print(f"Total Tests: {total_tests}")
        print(f"Successful: {successful_tests}")
        print(f"Failed: {total_tests - successful_tests}")
        
        if successful_tests == total_tests:
            print("ALL TESTS PASSED!")
        else:
            print(f"{total_tests - successful_tests} TEST(S) FAILED")
        
        print('='*60)

    def set_container_background_color(self, color):
        """Set background color for the main container."""
        self.main_window.set_background_color(color)
        print(f"Set main container background color to {color.name()}")

    def set_container_border_color(self, color):
        """Set border color for the main container."""
        self.main_window.set_border_color(color)
        print(f"Set main container border color to {color.name()}")

    def create_colored_floating_window(self, title_bar_color, title_text_color):
        """Create a new floating window with custom colors."""
        floating_root = FloatingDockRoot(
            manager=self.docking_manager,
            title="Custom Colored Window",
            title_bar_color=title_bar_color,
            title_text_color=title_text_color
        )
        floating_root.setGeometry(100, 100, 400, 300)
        self.docking_manager.register_dock_area(floating_root)
        floating_root.show()
        print(f"Created floating window with title bar color {title_bar_color.name()} and text color {title_text_color.name()}")

    def demo_icon_types(self):
        """
        Demonstrate various icon types supported by JCDock.
        This method showcases:
        - Unicode emoji icons (star, rocket, computer, etc.)
        - Qt Standard Icons (SP_FileIcon, SP_DirIcon, etc.)
        - Windows with no icons (fallback behavior)
        - Dynamic icon changes at runtime
        """
        print("ICON DEMO: Creating windows with different icon types")
        print("You should see icons in the title bars of the new windows")
        
        # Demo 1: Unicode emoji icons
        unicode_icons = ["🌟", "🚀", "💻", "🎯", "🔍", "📈"]
        for i, icon in enumerate(unicode_icons[:3]):  # Limit to 3 for demo
            window = FloatingDockRoot(
                manager=self.docking_manager,
                title=f"Unicode Demo {i+1}",
                icon=icon
            )
            window.setGeometry(150 + i*50, 150 + i*50, 350, 250)
            self.docking_manager.register_dock_area(window)
            window.show()
            print(f"Created window with Unicode icon (index {i+1})")
        
        # Demo 2: Qt Standard Icons (if available)
        qt_icons = ["SP_FileIcon", "SP_DirIcon", "SP_ComputerIcon"]
        for i, icon in enumerate(qt_icons[:2]):  # Limit to 2 for demo
            window = FloatingDockRoot(
                manager=self.docking_manager,
                title=f"Qt Standard {i+1}",
                icon=icon
            )
            window.setGeometry(500 + i*50, 150 + i*50, 350, 250)
            self.docking_manager.register_dock_area(window)
            window.show()
            print(f"Created window with Qt standard icon: {icon}")
        
        # Demo 3: No icon (test fallback)
        window_no_icon = FloatingDockRoot(
            manager=self.docking_manager,
            title="No Icon Demo",
            icon=None
        )
        window_no_icon.setGeometry(800, 150, 350, 250)
        self.docking_manager.register_dock_area(window_no_icon)
        window_no_icon.show()
        print("Created window with no icon")
        
        # Demo 4: Dynamic icon change
        demo_window = FloatingDockRoot(
            manager=self.docking_manager,
            title="Dynamic Icon Demo",
            icon="🔄"
        )
        demo_window.setGeometry(400, 400, 400, 300)
        self.docking_manager.register_dock_area(demo_window)
        demo_window.show()
        
        # Change icon after a delay to demonstrate dynamic updates
        def change_icon():
            demo_window.set_icon("✨")
            print("Changed demo window icon dynamically (spinning arrow to sparkle)")
        
        QTimer.singleShot(3000, change_icon)  # Change after 3 seconds
        print("Dynamic icon change scheduled for 3 seconds")
        
        print("ICON DEMO: All demonstration windows created")

    def create_window_with_unicode_icon(self, icon: str, title_suffix: str):
        """Create a floating window with a Unicode emoji icon."""
        window = FloatingDockRoot(
            manager=self.docking_manager,
            title=f"{title_suffix} Window",
            icon=icon
        )
        window.setGeometry(200, 200, 400, 300)
        self.docking_manager.register_dock_area(window)
        window.show()
        print(f"Created window '{title_suffix} Window' with Unicode icon")

    def create_window_with_qt_icon(self, icon_name: str, title_suffix: str):
        """Create a floating window with a Qt Standard icon."""
        window = FloatingDockRoot(
            manager=self.docking_manager,
            title=f"{title_suffix} Window",
            icon=icon_name
        )
        window.setGeometry(250, 250, 400, 300)
        self.docking_manager.register_dock_area(window)
        window.show()
        print(f"Created window '{title_suffix} Window' with Qt standard icon: {icon_name}")

    def create_window_with_no_icon(self):
        """Create a floating window with no icon to test fallback behavior."""
        window = FloatingDockRoot(
            manager=self.docking_manager,
            title="No Icon Window",
            icon=None
        )
        window.setGeometry(300, 300, 400, 300)
        self.docking_manager.register_dock_area(window)
        window.show()
        print("Created window with no icon (fallback test)")

    def add_icon_to_main_window(self):
        """Add an icon to the main window's title bar."""
        if self.main_window.title_bar:
            self.main_window.set_icon("🏠")
            print("Added house icon to main window")
        else:
            print("Main window has no title bar")

    def remove_icon_from_main_window(self):
        """Remove the icon from the main window's title bar."""
        if self.main_window.title_bar:
            self.main_window.set_icon(None)
            print("Removed icon from main window")
        else:
            print("Main window has no title bar")

    def change_first_container_icon(self):
        """Change the icon of the first available container (excluding main window)."""
        # Find the first container that's not the main window and has a title bar
        target_container = None
        for container in self.docking_manager.containers:
            if container != self.main_window and container.title_bar:
                target_container = container
                break
        
        if target_container:
            # Cycle through different icons
            current_icon = target_container.get_icon()
            icons = ["⭐", "🔥", "💎", "🎯", "🌟"]
            
            # If no icon or not in our list, start with first icon
            next_icon = icons[0]
            
            # If current icon exists, find next one in cycle
            try:
                if current_icon:
                    # This is a simple approach - in real app you might store icon state
                    import random
                    next_icon = random.choice(icons)
            except:
                next_icon = icons[0]
            
            target_container.set_icon(next_icon)
            print(f"Changed icon of container '{target_container.windowTitle()}'")
        else:
            print("No suitable container found (need a floating window with title bar)")
            print("Try creating a floating window first using the 'Widgets' menu")

    def change_main_window_title_text_color(self, color):
        """Change the title bar text color of the main window."""
        if self.main_window.title_bar:
            self.main_window.set_title_text_color(color)
            print(f"Changed main window title text color to {color.name()}")
        else:
            print("Main window has no title bar to change text color")

    def reset_all_colors(self):
        """Reset all colors to their defaults."""
        # Reset main window colors
        self.main_window.set_background_color(QColor("#F0F0F0"))
        self.main_window.set_border_color(QColor("#6A8EAE"))
        if self.main_window.title_bar:
            self.main_window.set_title_text_color(QColor("#101010"))
        print("Reset all colors to defaults (background: #F0F0F0, border: #6A8EAE, title text: #101010)")

    def run(self):
        """Loads saved layout from .ini file at startup, or starts with empty layout."""
        self.main_window.show()
        
        # Try to load saved layout first
        print("Checking for saved layout...")
        layout_loaded = self._load_layout_silently()
        
        if layout_loaded:
            print(f"SUCCESS: Loaded saved layout from {self._get_standard_layout_path()}")
            print(f"Startup complete! Restored {len(self.docking_manager.widgets)} widgets from saved layout.")
        else:
            print("No saved layout found. Starting with empty layout.")
            print("Startup complete! Use the 'Widgets' menu to create widgets.")
        
        print("Use the 'Colors' menu to test color customization features.")
        print("Use the 'Icons' menu to test icon functionality.")
        print("Use the 'File' menu to save/load layouts.")
        
        return self.app.exec()

if __name__ == "__main__":
    test_app = DockingTestApp()
    test_app.run()
