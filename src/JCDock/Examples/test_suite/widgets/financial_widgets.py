"""
Financial-themed widget classes for the JCDock test suite.
These widgets simulate trading application components like charts, orders, and portfolios.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QSpinBox, QLineEdit, QTextEdit
)
from PySide6.QtGui import QColor

from JCDock import persistable
from ..utils.data_generator import DataGenerator
from ..utils.constants import (
    CHART_ROWS, CHART_COLUMNS, ORDERS_ROWS, ORDERS_COLUMNS,
    PORTFOLIO_ROWS, PORTFOLIO_COLUMNS, MENU_LABELS, Colors
)


@persistable("chart_widget", "Chart Widget")
class ChartWidget(QWidget):
    """Chart widget displaying financial data in table format with controls."""
    
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Header with chart controls
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(MENU_LABELS['chart']))
        
        refresh_btn = QPushButton("Refresh Data")
        refresh_btn.clicked.connect(self._refresh_chart_data)
        header_layout.addWidget(refresh_btn)
        
        timeframe_btn = QPushButton("1D")
        timeframe_btn.clicked.connect(self._on_timeframe_changed)
        header_layout.addWidget(timeframe_btn)
        
        layout.addLayout(header_layout)
        
        # Chart data table
        self.chart_table = QTableWidget(CHART_ROWS, CHART_COLUMNS)
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
        zoom_in_btn = QPushButton("Zoom In")
        zoom_in_btn.clicked.connect(self._on_zoom_in)
        controls_layout.addWidget(zoom_in_btn)
        
        zoom_out_btn = QPushButton("Zoom Out")
        zoom_out_btn.clicked.connect(self._on_zoom_out)
        controls_layout.addWidget(zoom_out_btn)
        
        export_btn = QPushButton("Export Chart")
        export_btn.clicked.connect(self._on_export_chart)
        controls_layout.addWidget(export_btn)
        
        layout.addLayout(controls_layout)
    
    def _populate_chart_data(self):
        """Populate chart table with financial data."""
        chart_data = DataGenerator.generate_chart_data()
        DataGenerator.populate_chart_table(self.chart_table, chart_data)
    
    def _refresh_chart_data(self):
        """Refresh chart data with new values."""
        self._populate_chart_data()
        print("Chart data refreshed")
    
    def _on_timeframe_changed(self):
        """Handle timeframe button click."""
        print("Timeframe changed")
    
    def _on_zoom_in(self):
        """Handle zoom in button click."""
        print("Zoom in clicked")
    
    def _on_zoom_out(self):
        """Handle zoom out button click."""
        print("Zoom out clicked")
    
    def _on_export_chart(self):
        """Handle export chart button click."""
        print("Export chart clicked")


@persistable("order_widget", "Order Widget")
class OrderWidget(QWidget):
    """Order management widget for trading operations."""
    
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(MENU_LABELS['orders']))
        
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
        self.symbol_field.clicked.connect(self._on_symbol_selector)
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
        self.orders_table = QTableWidget(ORDERS_ROWS, ORDERS_COLUMNS)
        self.orders_table.setHorizontalHeaderLabels([
            "Order ID", "Symbol", "Side", "Quantity", "Price", "Status"
        ])
        
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
        status_layout.addWidget(QLabel(MENU_LABELS['active_orders'] + ": 5"))
        status_layout.addWidget(QLabel(MENU_LABELS['total_value'] + ": $15,750"))
        status_layout.addWidget(QLabel(MENU_LABELS['connected']))
        layout.addLayout(status_layout)
    
    def _populate_orders_data(self):
        """Populate orders table with order data."""
        orders_data = DataGenerator.generate_orders_data()
        DataGenerator.populate_orders_table(self.orders_table, orders_data)
    
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
    
    def _on_symbol_selector(self):
        """Handle symbol selector click."""
        print("Symbol selector opened")


@persistable("portfolio_widget", "Portfolio Widget")
class PortfolioWidget(QWidget):
    """Portfolio overview widget showing holdings and performance."""
    
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Header with portfolio summary
        header_layout = QVBoxLayout()
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel(MENU_LABELS['portfolio']))
        
        sync_btn = QPushButton("Sync")
        sync_btn.clicked.connect(self._sync_portfolio)
        title_layout.addWidget(sync_btn)
        
        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._on_settings_clicked)
        title_layout.addWidget(settings_btn)
        
        header_layout.addLayout(title_layout)
        
        # Portfolio summary
        summary_layout = QHBoxLayout()
        summary_layout.addWidget(QLabel(MENU_LABELS['total_value'] + ": $125,750.00"))
        summary_layout.addWidget(QLabel(MENU_LABELS['day_pnl'] + ": +$2,150 (+1.74%)"))
        summary_layout.addWidget(QLabel(MENU_LABELS['total_pnl'] + ": +$15,750 (+14.3%)"))
        header_layout.addLayout(summary_layout)
        
        layout.addLayout(header_layout)
        
        # Holdings table
        self.portfolio_table = QTableWidget(PORTFOLIO_ROWS, PORTFOLIO_COLUMNS)
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
        add_btn = QPushButton("Add Position")
        add_btn.clicked.connect(self._on_add_position)
        actions_layout.addWidget(add_btn)
        
        rebalance_btn = QPushButton("Rebalance")
        rebalance_btn.clicked.connect(self._on_rebalance)
        actions_layout.addWidget(rebalance_btn)
        
        report_btn = QPushButton("Generate Report")
        report_btn.clicked.connect(self._on_generate_report)
        actions_layout.addWidget(report_btn)
        
        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self._on_export_csv)
        actions_layout.addWidget(export_btn)
        
        layout.addLayout(actions_layout)
        
        # Footer with allocation chart (simulated with labels)
        allocation_layout = QHBoxLayout()
        allocation_layout.addWidget(QLabel("Asset Allocation:"))
        allocation_layout.addWidget(QLabel(MENU_LABELS['stocks'] + " 75%"))
        allocation_layout.addWidget(QLabel(MENU_LABELS['bonds'] + " 15%"))
        allocation_layout.addWidget(QLabel(MENU_LABELS['cash'] + " 10%"))
        layout.addLayout(allocation_layout)
    
    def _populate_portfolio_data(self):
        """Populate portfolio table with holdings data."""
        portfolio_data = DataGenerator.generate_portfolio_data()
        DataGenerator.populate_portfolio_table(self.portfolio_table, portfolio_data)
    
    def _sync_portfolio(self):
        """Sync portfolio data."""
        print("Syncing portfolio data...")
        self._populate_portfolio_data()
        print("Portfolio data updated")
    
    def _on_settings_clicked(self):
        """Handle settings button click."""
        print("Portfolio settings opened")
    
    def _on_add_position(self):
        """Handle add position button click."""
        print("Add position clicked")
    
    def _on_rebalance(self):
        """Handle rebalance button click."""
        print("Rebalance clicked")
    
    def _on_generate_report(self):
        """Handle generate report button click."""
        print("Generate report clicked")
    
    def _on_export_csv(self):
        """Handle export CSV button click."""
        print("Export CSV clicked")