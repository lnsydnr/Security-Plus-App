"""
Launcher for Security+ Study App. Keeps a small entrypoint that initializes the DB
and starts the GUI. The main GUI lives in `gui.py` and core logic in `app_core.py`.
"""
import sys
from app_core import init_db
from gui import MainWindow
from PySide6.QtWidgets import QApplication

def main():
    init_db()
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
