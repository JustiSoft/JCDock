"""
Main entry point for the refactored JCDock test suite.
This replaces the original dock_test.py with a modular, well-structured application.
"""

from .app import DockingTestApp


def main():
    """Main entry point for the test suite application."""
    test_app = DockingTestApp()
    return test_app.run()


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)