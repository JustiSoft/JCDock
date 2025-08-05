"""
Parameterized Widget Save/Load Demo - JCDock Simple Example

This script demonstrates:
- Creating widgets with constructor parameters (symbol, timeframe, indicators)
- Saving layouts that preserve widget constructor parameters  
- Loading layouts and restoring widgets with their original parameters
- Complete parameter persistence workflow using get_dock_state()/set_dock_state()

Shows how to create financial chart widgets with specific parameters like TSLA/1H
that maintain their configuration after save/load cycles.
"""

import sys
import os
import base64
import configparser
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QPushButton, QMenuBar, QTableWidget, 
                               QTableWidgetItem, QComboBox)
from PySide6.QtGui import QAction, QFont
from PySide6.QtCore import Qt
from JCDock.core.docking_manager import DockingManager
from JCDock.widgets.dock_container import DockContainer
from JCDock import persistable


# Register each chart type that we'll create
from JCDock.core.widget_registry import get_registry

@persistable("financial_chart", "Financial Chart")
class FinancialChartWidget(QWidget):
    """Financial chart widget with constructor parameters for demonstration."""
    
    def __init__(self, symbol=None, timeframe=None, indicators=None):
        super().__init__()
        
        # Store constructor parameters as instance variables
        self.symbol = symbol or "AAPL"
        self.timeframe = timeframe or "1D"
        self.indicators = indicators or []
        
        # Additional widget state
        self.last_updated = None
        self.chart_data = []
        
        # Initialize UI based on current parameters
        self._setup_ui()
        self._generate_sample_data()

    def _setup_ui(self):
        """Setup the widget UI using current parameters."""
        # Clear existing layout if rebuilding
        if self.layout():
            while self.layout().count():
                child = self.layout().takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        else:
            layout = QVBoxLayout(self)
        
        layout = self.layout()
        
        # Header with symbol and timeframe
        header_layout = QHBoxLayout()
        
        # Symbol label (bold, larger font)
        symbol_label = QLabel(f"Chart: {self.symbol}")
        symbol_font = QFont()
        symbol_font.setBold(True)
        symbol_font.setPointSize(14)
        symbol_label.setFont(symbol_font)
        symbol_label.setStyleSheet("color: #2c3e50; padding: 5px;")
        header_layout.addWidget(symbol_label)
        
        # Timeframe label
        timeframe_label = QLabel(f"Timeframe: {self.timeframe}")
        timeframe_label.setStyleSheet("color: #666; font-weight: bold; padding: 5px;")
        header_layout.addWidget(timeframe_label)
        
        # Indicators label
        indicators_text = ", ".join(self.indicators) if self.indicators else "None"
        indicators_label = QLabel(f"Indicators: {indicators_text}")
        indicators_label.setStyleSheet("color: #666; padding: 5px;")
        header_layout.addWidget(indicators_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Status information
        status_layout = QHBoxLayout()
        if self.last_updated:
            status_label = QLabel(f"Last Updated: {self.last_updated}")
            status_label.setStyleSheet("color: #888; font-size: 10px; padding: 2px;")
            status_layout.addWidget(status_label)
        
        data_points_label = QLabel(f"Data Points: {len(self.chart_data)}")
        data_points_label.setStyleSheet("color: #888; font-size: 10px; padding: 2px;")
        status_layout.addWidget(data_points_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # Chart data table
        self.data_table = QTableWidget(10, 4)
        self.data_table.setHorizontalHeaderLabels(["Time", "Price", "Volume", "Change %"])
        
        # Style the table
        self.data_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #ddd;
                background-color: #fafafa;
                alternate-background-color: #f0f0f0;
                border: 1px solid #ccc;
            }
            QHeaderView::section {
                background-color: #e0e0e0;
                font-weight: bold;
                border: 1px solid #bbb;
                padding: 4px;
            }
        """)
        self.data_table.setAlternatingRowColors(True)
        
        self._populate_table()
        layout.addWidget(self.data_table)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh Data")
        refresh_btn.clicked.connect(self._refresh_data)
        controls_layout.addWidget(refresh_btn)
        
        settings_btn = QPushButton("Chart Settings")
        settings_btn.clicked.connect(self._show_settings)
        controls_layout.addWidget(settings_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)

    def _generate_sample_data(self):
        """Generate sample financial data based on symbol."""
        import random
        
        # Base prices for different symbols
        base_prices = {
            "AAPL": 150.0,
            "TSLA": 200.0,
            "MSFT": 300.0,
            "GOOGL": 2500.0,
            "AMZN": 3000.0
        }
        
        base_price = base_prices.get(self.symbol, 100.0)
        
        self.chart_data = []
        for i in range(10):
            price = base_price + random.uniform(-10, 10)
            volume = random.randint(1000000, 10000000)
            change_pct = random.uniform(-3.0, 3.0)
            
            self.chart_data.append({
                'time': f"09:{30 + i * 5:02d}",
                'price': f"${price:.2f}",
                'volume': f"{volume:,}",
                'change_pct': f"{change_pct:+.2f}%"
            })
        
        self.last_updated = datetime.now().strftime('%H:%M:%S')

    def _populate_table(self):
        """Populate the data table with chart data."""
        for row, data_point in enumerate(self.chart_data):
            self.data_table.setItem(row, 0, QTableWidgetItem(data_point['time']))
            self.data_table.setItem(row, 1, QTableWidgetItem(data_point['price']))
            self.data_table.setItem(row, 2, QTableWidgetItem(data_point['volume']))
            
            # Color code the change percentage
            change_item = QTableWidgetItem(data_point['change_pct'])
            if data_point['change_pct'].startswith('+'):
                change_item.setBackground(Qt.GlobalColor.green)
            elif data_point['change_pct'].startswith('-'):
                change_item.setBackground(Qt.GlobalColor.red)
            
            self.data_table.setItem(row, 3, change_item)

    def _refresh_data(self):
        """Refresh chart data."""
        self._generate_sample_data()
        self._populate_table()
        print(f"Refreshed data for {self.symbol} ({self.timeframe})")

    def _show_settings(self):
        """Show chart settings (placeholder)."""
        print(f"Chart settings for {self.symbol} - {self.timeframe} - Indicators: {self.indicators}")

    def get_dock_state(self):
        """Save all constructor parameters and widget state."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'indicators': self.indicators,
            'last_updated': self.last_updated,
            'chart_data': self.chart_data
        }

    def set_dock_state(self, state_dict):
        """Restore constructor parameters and widget state."""
        if not isinstance(state_dict, dict):
            return
        
        # Restore constructor parameters
        self.symbol = state_dict.get('symbol', 'AAPL')
        self.timeframe = state_dict.get('timeframe', '1D')
        self.indicators = state_dict.get('indicators', [])
        
        # Restore widget state
        self.last_updated = state_dict.get('last_updated')
        self.chart_data = state_dict.get('chart_data', [])
        
        # Recreate UI with restored parameters
        self._setup_ui()
        self._populate_table()


# Widget is now registered automatically via @persistable decorator


def main():
    # Create the Qt application
    app = QApplication(sys.argv)
    
    # Widget types are now registered automatically via @persistable decorator
    
    # Create the docking manager
    manager = DockingManager()
    
    # Widget registration verified via @persistable decorator
    
    # Create main window using unified API
    main_window = manager.create_window(
        is_main_window=True,
        title="JCDock Enhanced Auto-Registration Demo",
        x=100, y=100, width=800, height=600,
        auto_persistent_root=True,
        preserve_title=True
    )
    main_window.setObjectName("MainWindow")
    
    # Add menu bar
    menu_bar = QMenuBar(main_window)
    main_window.layout().insertWidget(1, menu_bar)
    
    # File menu
    file_menu = menu_bar.addMenu("File")
    
    save_action = QAction("Save Layout", main_window)
    load_action = QAction("Load Layout", main_window)
    file_menu.addAction(save_action)
    file_menu.addAction(load_action)
    file_menu.addSeparator()
    
    exit_action = QAction("Exit", main_window)
    exit_action.triggered.connect(app.quit)
    file_menu.addAction(exit_action)
    
    # Charts menu with parameterized options
    charts_menu = menu_bar.addMenu("Charts")
    
    # Predefined chart configurations
    chart_configs = [
        ("TSLA 1-Hour with RSI+SMA", "TSLA", "1H", ["RSI", "SMA"]),
        ("AAPL 5-Minute with MACD", "AAPL", "5M", ["MACD"]),
        ("MSFT Daily with Bollinger Bands", "MSFT", "1D", ["BB"]),
        ("GOOGL 15-Minute Clean", "GOOGL", "15M", []),
        ("AMZN Weekly with All Indicators", "AMZN", "1W", ["RSI", "SMA", "MACD", "BB"])
    ]
    
    for config_name, symbol, timeframe, indicators in chart_configs:
        action = QAction(config_name, main_window)
        # Use lambda with default parameter to capture the values
        action.triggered.connect(
            lambda checked, s=symbol, tf=timeframe, ind=indicators, name=config_name: 
            create_chart_widget(manager, s, tf, ind, name)
        )
        charts_menu.addAction(action)
    
    # Layout file path (INI format)
    layout_file = os.path.join(os.getcwd(), "parameterized_demo_layout.ini")
    
    def save_layout_to_ini():
        """Save current layout to INI file."""
        try:
            # Get binary layout data
            layout_data = manager.save_layout_to_bytearray()
            
            # Encode binary data as base64 for INI storage
            layout_b64 = base64.b64encode(layout_data).decode('utf-8')
            
            # Create INI config
            config = configparser.ConfigParser()
            config['Layout'] = {
                'version': '1.0',
                'saved_at': datetime.now().isoformat(),
                'data': layout_b64
            }
            
            # Add application info
            config['Application'] = {
                'name': 'JCDock Enhanced Auto-Registration Demo',
                'description': 'Layout with financial chart widgets using enhanced auto-registration with smart factories'
            }
            
            # Save to INI file
            with open(layout_file, 'w') as f:
                config.write(f)
                
            print(f"Layout saved to: {layout_file}")
            
        except Exception as e:
            print(f"Failed to save layout: {e}")
    
    def load_layout_from_ini():
        """Load layout from INI file."""
        try:
            if os.path.exists(layout_file):
                # Read INI config
                config = configparser.ConfigParser()
                config.read(layout_file)
                
                # Get layout data
                if 'Layout' in config and 'data' in config['Layout']:
                    layout_b64 = config['Layout']['data']
                    layout_data = base64.b64decode(layout_b64.encode('utf-8'))
                    
                    # Load layout - this handles all widget/container creation and display
                    manager.load_layout_from_bytearray(layout_data)
                    
                    saved_at = config['Layout'].get('saved_at', 'Unknown')
                    print(f"Layout loaded from: {layout_file}")
                    print(f"Saved at: {saved_at}")
                else:
                    print(f"Invalid INI file format: {layout_file}")
            else:
                print("No layout file found - use Charts menu to create widgets.")
                
        except Exception as e:
            print(f"Failed to load layout: {e}")
            print("Use Charts menu to create widgets.")
    
    def create_chart_widget(manager, symbol, timeframe, indicators, config_name):
        """Create a new chart widget - testing enhanced auto-registration."""
        # Create widget instance with parameters
        widget_instance = FinancialChartWidget(
            symbol=symbol,
            timeframe=timeframe, 
            indicators=indicators
        )
        
        print(f"Creating chart widget with enhanced auto-registration: {symbol} {timeframe}...")
        
        # Use auto-generated key approach with enhanced smart factory
        container = manager.create_window(
            widget_instance,
            # No key parameter - let enhanced library auto-generate and register intelligently
            title=f"{symbol} {timeframe}",
            x=300, y=300,
            width=400, height=300,
            persist=True
        )
        
        panel = container.contained_widgets[0] if container.contained_widgets else None
        auto_key = panel.persistent_id if panel else "unknown"
        print(f"SUCCESS: Auto-generated key with smart factory: {auto_key}")
        print(f"Widget created: {symbol} {timeframe} - Parameters captured for persistence")
    
    # Connect menu actions
    save_action.triggered.connect(save_layout_to_ini)
    load_action.triggered.connect(load_layout_from_ini)
    
    # Connect to application_closing signal to save layout automatically
    def save_layout_on_app_closing(layout_data):
        """Save layout when application is closing (called by library)."""
        try:
            layout_b64 = base64.b64encode(layout_data).decode('utf-8')
            
            config = configparser.ConfigParser()
            config['Layout'] = {
                'version': '1.0',
                'saved_at': datetime.now().isoformat(),
                'data': layout_b64
            }
            
            config['Application'] = {
                'name': 'JCDock Enhanced Auto-Registration Demo',
                'description': 'Layout with financial chart widgets using enhanced auto-registration with smart factories'
            }
            
            with open(layout_file, 'w') as f:
                config.write(f)
                
            print(f"Layout auto-saved on application close")
            
        except Exception as e:
            print(f"Failed to save layout on app close: {e}")
    
    # Connect to the library's application_closing signal
    manager.signals.application_closing.connect(save_layout_on_app_closing)
    
    # Auto-load layout on startup
    try:
        load_layout_from_ini()
    except Exception as e:
        print(f"Error loading layout: {e}")
        print("Use the Charts menu to create widgets.")
    
    # Show main window
    main_window.show()
    
    print("\n" + "="*70)
    print("ENHANCED AUTO-REGISTRATION DEMO - Smart Factories for Parameterized Widgets")
    print("="*70)
    print("NEW FEATURES:")
    print("- Enhanced auto-registration with intelligent parameter detection")
    print("- Smart factory functions that capture constructor parameters")
    print("- Automatic state capture and restoration for complex widgets")
    print("- Works seamlessly with parameterized widgets like FinancialChartWidget")
    print()
    print("HOW IT WORKS:")
    print("- Uses Python's inspect module to analyze widget constructors")
    print("- Captures constructor parameters from existing widget instances")
    print("- Creates smart factory functions that preserve parameters")
    print("- Combines constructor recreation with get_dock_state()/set_dock_state()")
    print()
    print("INSTRUCTIONS:")
    print("1. Create charts using Charts menu - no explicit keys needed!")
    print("   - Auto-generated keys: FinancialChartWidget_1, FinancialChartWidget_2, etc.")
    print("   - Each widget's parameters are automatically captured")
    print()
    print("2. Save and reload layout to test enhanced persistence")
    print("   - Widgets should restore with their ORIGINAL parameters")
    print("   - No more key mismatch errors!")
    print()
    print("3. Parameters are preserved: symbol, timeframe, indicators")
    print("   - TSLA 1H widgets restore as TSLA 1H (not default AAPL 1D)")
    print()
    print("RESULT: Auto-generated keys now work perfectly with parameterized widgets!")
    print("="*70)
    
    # Run the application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())