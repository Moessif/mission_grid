from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def run():
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
