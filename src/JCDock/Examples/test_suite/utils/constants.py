"""
Constants and configuration values for the JCDock test suite.
Centralizes magic numbers and commonly used values.
"""

from PySide6.QtCore import QSize, QPoint
from PySide6.QtGui import QColor

# Window and Widget Configuration
DEFAULT_WINDOW_SIZE = QSize(400, 300)
LARGE_WINDOW_SIZE = QSize(800, 600)
CASCADE_OFFSET = 40
DEFAULT_POSITION = QPoint(200, 200)
MAIN_WINDOW_POSITION = QPoint(300, 300)

# Financial Data Generation
BASE_PRICE = 150.0
PRICE_VARIANCE = 2.5
MIN_VOLUME = 10000
MAX_VOLUME = 500000
DYNAMIC_ITEMS_COUNT = 5

# UI Constants
TABLE_ROWS_DEFAULT = 5
TABLE_COLUMNS_DEFAULT = 3
CHART_ROWS = 12
CHART_COLUMNS = 4
ORDERS_ROWS = 8
ORDERS_COLUMNS = 6
PORTFOLIO_ROWS = 10
PORTFOLIO_COLUMNS = 7

# Color Schemes
class Colors:
    # Default colors
    DEFAULT_BACKGROUND = QColor("#F0F0F0")
    DEFAULT_BORDER = QColor("#6A8EAE")
    DEFAULT_TITLE_TEXT = QColor("#101010")
    
    # Status colors
    SUCCESS_GREEN = QColor("#28a745")
    ERROR_RED = QColor("#dc3545")
    WARNING_YELLOW = QColor("#fff3cd")
    INFO_BLUE = QColor("#007bff")
    
    # Background colors for status
    SUCCESS_BG = QColor("#d4edda")
    ERROR_BG = QColor("#f8d7da")
    WARNING_BG = QColor("#fff3cd")
    NEUTRAL_BG = QColor("#f8f9fa")
    
    # Test colors
    LIGHT_BLUE = QColor("#E6F3FF")
    DARK_BLUE = QColor("#0066CC")
    FOREST_GREEN = QColor("#228B22")
    SLATE_BLUE = QColor("#6A5ACD")
    DARK_GRAY = QColor("#2D2D2D")
    BRIGHT_GREEN = QColor("#00FF00")
    RED = QColor("#FF0000")
    BLUE = QColor("#0066FF")
    GOLD = QColor("#FFD700")
    PURPLE = QColor("#DDA0DD")
    LIGHT_GREEN = QColor("#90EE90")

# Icon Sets
UNICODE_ICONS = ["🌟", "🚀", "💻", "🎯", "🔍", "📈", "🏠", "⚙️", "📊"]
QT_STANDARD_ICONS = ["SP_FileIcon", "SP_DirIcon", "SP_ComputerIcon"]
DYNAMIC_ICONS = ["⭐", "🔥", "💎", "🎯", "🌟"]

# Financial Data
SAMPLE_SYMBOLS = ["AAPL", "GOOGL", "TSLA", "MSFT", "AMZN", "NVDA", "META", "NFLX", "DIS", "V"]
ORDER_STATUSES = ["Pending", "Filled", "Cancelled", "Partial"]
ORDER_SIDES = ["BUY", "SELL"]

# Test Configuration
TEST_BATCH_SIZE = 3
TEST_DELAY_MS = 3000

# Layout Configuration
LAYOUT_FILE_NAME = "jcdock_layout.ini"
LAYOUT_VERSION = "1.0"
APPLICATION_NAME = "JCDock Test Application"

# Menu Labels - replacing Unicode with ASCII for Windows compatibility
MENU_LABELS = {
    'chart': '[CHART] Stock Price Chart',
    'orders': '[ORDERS] Order Management', 
    'portfolio': '[PORTFOLIO] Portfolio Overview',
    'total_value': '[VALUE] Total Value',
    'day_pnl': '[P&L] Day P&L',
    'total_pnl': '[TOTAL] Total P&L',
    'active_orders': '[ACTIVE] Active Orders',
    'connected': '[ONLINE] Connected',
    'stocks': '[STOCKS] Stocks',
    'bonds': '[BONDS] Bonds', 
    'cash': '[CASH] Cash'
}