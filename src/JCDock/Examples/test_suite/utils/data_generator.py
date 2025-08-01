"""
Data generation utilities for the JCDock test suite.
Centralizes data generation logic to reduce code duplication.
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Any
from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .constants import (
    BASE_PRICE, PRICE_VARIANCE, MIN_VOLUME, MAX_VOLUME,
    SAMPLE_SYMBOLS, ORDER_STATUSES, ORDER_SIDES, Colors
)


class DataGenerator:
    """Utility class for generating test data."""
    
    @staticmethod
    def generate_table_data(rows: int, columns: int, prefix: str) -> List[List[str]]:
        """Generate generic table data with the specified dimensions."""
        data = []
        for row in range(rows):
            row_data = []
            for col in range(columns):
                if col == 0:  # ID column
                    row_data.append(f"{prefix}-I{row+1}")
                elif col == 1:  # Description column
                    row_data.append(f"Sample data item for row {row+1}")
                else:  # Value column
                    row_data.append(str(random.randint(100, 999)))
            data.append(row_data)
        return data
    
    @staticmethod
    def populate_table_widget(table_widget, data: List[List[str]], center_align_columns: List[int] = None):
        """Populate a QTableWidget with data."""
        if center_align_columns is None:
            center_align_columns = [0, 2]  # Default: center align first and last columns
            
        for row, row_data in enumerate(data):
            for col, cell_value in enumerate(row_data):
                item = QTableWidgetItem(str(cell_value))
                if col in center_align_columns:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table_widget.setItem(row, col, item)
        
        table_widget.resizeColumnsToContents()
    
    @staticmethod
    def generate_chart_data() -> List[Dict[str, Any]]:
        """Generate financial chart data."""
        chart_data = []
        base_price = BASE_PRICE
        
        for hour_offset in range(12):
            time_str = (datetime.now() - timedelta(hours=11-hour_offset)).strftime("%H:%M")
            
            # Simulate price movement
            price_change = random.uniform(-PRICE_VARIANCE, PRICE_VARIANCE)
            current_price = base_price + price_change
            base_price = current_price
            
            volume = random.randint(MIN_VOLUME, MAX_VOLUME)
            change_pct = price_change / current_price * 100
            
            chart_data.append({
                'time': time_str,
                'price': current_price,
                'volume': volume,
                'change_pct': change_pct
            })
        
        return chart_data
    
    @staticmethod
    def populate_chart_table(table_widget, chart_data: List[Dict[str, Any]]):
        """Populate chart table with financial data."""
        for row, data in enumerate(chart_data):
            table_widget.setItem(row, 0, QTableWidgetItem(data['time']))
            table_widget.setItem(row, 1, QTableWidgetItem(f"${data['price']:.2f}"))
            table_widget.setItem(row, 2, QTableWidgetItem(f"{data['volume']:,}"))
            
            # Color code the change percentage
            change_item = QTableWidgetItem(f"{data['change_pct']:+.2f}%")
            if data['change_pct'] > 0:
                change_item.setBackground(Colors.SUCCESS_BG)
            elif data['change_pct'] < 0:
                change_item.setBackground(Colors.ERROR_BG)
            table_widget.setItem(row, 3, change_item)
        
        table_widget.resizeColumnsToContents()
    
    @staticmethod
    def generate_orders_data() -> List[Dict[str, Any]]:
        """Generate order data for trading widget."""
        orders = []
        
        for i in range(8):
            order_id = f"ORD{1000 + i}"
            symbol = random.choice(SAMPLE_SYMBOLS)
            side = random.choice(ORDER_SIDES)
            quantity = random.randint(10, 500)
            price = random.uniform(50, 300)
            status = random.choice(ORDER_STATUSES)
            
            orders.append({
                'order_id': order_id,
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'price': price,
                'status': status
            })
        
        return orders
    
    @staticmethod
    def populate_orders_table(table_widget, orders_data: List[Dict[str, Any]]):
        """Populate orders table with trading data."""
        for row, order in enumerate(orders_data):
            table_widget.setItem(row, 0, QTableWidgetItem(order['order_id']))
            table_widget.setItem(row, 1, QTableWidgetItem(order['symbol']))
            
            # Color code buy/sell
            side_item = QTableWidgetItem(order['side'])
            if order['side'] == "BUY":
                side_item.setForeground(Colors.SUCCESS_GREEN)
            else:
                side_item.setForeground(Colors.ERROR_RED)
            table_widget.setItem(row, 2, side_item)
            
            table_widget.setItem(row, 3, QTableWidgetItem(str(order['quantity'])))
            table_widget.setItem(row, 4, QTableWidgetItem(f"${order['price']:.2f}"))
            
            # Color code status
            status_item = QTableWidgetItem(order['status'])
            if order['status'] == "Filled":
                status_item.setBackground(Colors.SUCCESS_BG)
            elif order['status'] == "Cancelled":
                status_item.setBackground(Colors.ERROR_BG)
            elif order['status'] == "Pending":
                status_item.setBackground(Colors.WARNING_BG)
            table_widget.setItem(row, 5, status_item)
        
        table_widget.resizeColumnsToContents()
    
    @staticmethod
    def generate_portfolio_data() -> List[Dict[str, Any]]:
        """Generate portfolio holdings data."""
        holdings = [
            ("AAPL", 150), ("GOOGL", 50), ("TSLA", 75), ("MSFT", 200),
            ("AMZN", 30), ("NVDA", 100), ("META", 80), ("NFLX", 25),
            ("DIS", 120), ("V", 90)
        ]
        
        portfolio_data = []
        for symbol, shares in holdings:
            avg_cost = random.uniform(50, 300)
            current_price = avg_cost * random.uniform(0.8, 1.4)  # ±40% from cost
            market_value = shares * current_price
            pnl_dollar = shares * (current_price - avg_cost)
            pnl_percent = (current_price - avg_cost) / avg_cost * 100
            
            portfolio_data.append({
                'symbol': symbol,
                'shares': shares,
                'avg_cost': avg_cost,
                'current_price': current_price,
                'market_value': market_value,
                'pnl_dollar': pnl_dollar,
                'pnl_percent': pnl_percent
            })
        
        return portfolio_data
    
    @staticmethod
    def populate_portfolio_table(table_widget, portfolio_data: List[Dict[str, Any]]):
        """Populate portfolio table with holdings data."""
        for row, holding in enumerate(portfolio_data):
            table_widget.setItem(row, 0, QTableWidgetItem(holding['symbol']))
            table_widget.setItem(row, 1, QTableWidgetItem(str(holding['shares'])))
            table_widget.setItem(row, 2, QTableWidgetItem(f"${holding['avg_cost']:.2f}"))
            table_widget.setItem(row, 3, QTableWidgetItem(f"${holding['current_price']:.2f}"))
            table_widget.setItem(row, 4, QTableWidgetItem(f"${holding['market_value']:,.2f}"))
            
            # Color code P&L
            pnl_dollar_item = QTableWidgetItem(f"${holding['pnl_dollar']:+,.2f}")
            pnl_percent_item = QTableWidgetItem(f"{holding['pnl_percent']:+.1f}%")
            
            if holding['pnl_dollar'] > 0:
                pnl_dollar_item.setForeground(Colors.SUCCESS_GREEN)
                pnl_percent_item.setForeground(Colors.SUCCESS_GREEN)
                pnl_dollar_item.setBackground(QColor("#f8fff9"))
                pnl_percent_item.setBackground(QColor("#f8fff9"))
            else:
                pnl_dollar_item.setForeground(Colors.ERROR_RED)
                pnl_percent_item.setForeground(Colors.ERROR_RED)
                pnl_dollar_item.setBackground(QColor("#fff5f5"))
                pnl_percent_item.setBackground(QColor("#fff5f5"))
            
            table_widget.setItem(row, 5, pnl_dollar_item)
            table_widget.setItem(row, 6, pnl_percent_item)
        
        table_widget.resizeColumnsToContents()