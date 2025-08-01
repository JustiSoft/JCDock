"""
Layout management functionality for the JCDock test suite.
Handles saving, loading, and managing layout persistence.
"""

import os
import base64
import configparser
from datetime import datetime
from typing import Optional

from ..utils.constants import LAYOUT_FILE_NAME, LAYOUT_VERSION, APPLICATION_NAME


class LayoutManager:
    """Manages layout saving and loading operations."""
    
    def __init__(self, docking_manager, main_window):
        self.docking_manager = docking_manager
        self.main_window = main_window
        self.saved_layout_data = None
    
    def get_standard_layout_path(self) -> str:
        """Return the standardized path for the application layout file."""
        layouts_dir = os.path.join(os.getcwd(), "layouts")
        return os.path.join(layouts_dir, LAYOUT_FILE_NAME)
    
    def ensure_layout_directory(self):
        """Create the layouts directory if it doesn't exist."""
        layouts_dir = os.path.join(os.getcwd(), "layouts")
        if not os.path.exists(layouts_dir):
            os.makedirs(layouts_dir)
    
    def save_layout(self):
        """Save the current docking layout to the standardized .ini file."""
        print("\n--- RUNNING TEST: Save Layout ---")
        
        # Use standardized file path
        file_path = self.get_standard_layout_path()
        
        try:
            # Ensure the directory exists
            self.ensure_layout_directory()
            
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
                'version': LAYOUT_VERSION,
                'application': APPLICATION_NAME
            }
            
            # Write to file
            with open(file_path, 'w') as configfile:
                config.write(configfile)
            
            print(f"SUCCESS: Layout saved to {file_path}")
            
        except Exception as e:
            print(f"FAILURE: Could not save layout: {e}")
        print("-" * 35)
    
    def load_layout(self):
        """Load a docking layout from the standardized .ini file."""
        print("\n--- RUNNING TEST: Load Layout ---")
        
        # Use standardized file path
        file_path = self.get_standard_layout_path()
        
        if not os.path.exists(file_path):
            print(f"INFO: No saved layout found at {file_path}")
            print("-" * 35)
            return
        
        try:
            # Read .ini file
            config = configparser.ConfigParser()
            config.read(file_path)
            
            # Validate file structure
            if 'layout' not in config:
                print("FAILURE: Invalid layout file - missing [layout] section")
                print("-" * 35)
                return
            
            if 'data' not in config['layout']:
                print("FAILURE: Invalid layout file - missing layout data")
                print("-" * 35)
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
        print("-" * 35)
    
    def load_layout_silently(self) -> bool:
        """
        Silently load a docking layout from the standardized .ini file.
        Used for startup loading without test output.
        
        Returns:
            bool: True if layout was loaded successfully, False otherwise
        """
        file_path = self.get_standard_layout_path()
        
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