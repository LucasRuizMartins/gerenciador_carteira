"""
Módulo da interface gráfica (PySide6) do sistema de carteiras.

Entry point:
    python -m src.gui
"""
from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

def main() -> None:
    from src.gui.main_window import MainWindow
    from src.gui.styles import GLOBAL_STYLESHEET

    app = QApplication(sys.argv)
    app.setApplicationName("Carmel Capital — Gestão de Carteiras")
    app.setStyleSheet(GLOBAL_STYLESHEET)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
