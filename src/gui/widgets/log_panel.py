"""
LogPanel — QPlainTextEdit que captura o logger do sistema e exibe
linhas coloridas por nível (INFO, WARNING, ERROR) em tempo real.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QWidget


class _QtLogHandler(logging.Handler, QObject):
    """Handler de logging que emite um sinal Qt por linha."""
    nova_linha = Signal(int, str)  # level, message

    def __init__(self) -> None:
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        try:
            msg = self.format(record)
            self.nova_linha.emit(record.levelno, msg)
        except Exception:
            self.handleError(record)


class LogPanel(QPlainTextEdit):
    """
    Painel de log em tempo real.

    Conecta-se ao logger raiz do Python e exibe mensagens coloridas:
      INFO    → branco/cinza
      WARNING → amarelo
      ERROR   → vermelho
      CRITICAL→ vermelho brilhante

    Uso:
        panel = LogPanel(parent)
        panel.instalar()   # conecta ao logger raiz
    """

    LEVEL_COLORS = {
        logging.DEBUG:    "#9e9eb3",
        logging.INFO:     "#e8eaf6",
        logging.WARNING:  "#f0a500",
        logging.ERROR:    "#f05252",
        logging.CRITICAL: "#ff1f1f",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("log_panel")
        self.setReadOnly(True)
        self.setMaximumBlockCount(1000)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._handler = _QtLogHandler()
        self._handler.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s",
                              datefmt="%H:%M:%S")
        )
        self._handler.nova_linha.connect(self._append_line)

    def instalar(self, logger_name: str | None = None) -> None:
        """Conecta ao logger especificado (ou raiz se None)."""
        target = logging.getLogger(logger_name)
        target.addHandler(self._handler)
        if target.level == logging.NOTSET:
            target.setLevel(logging.DEBUG)

    def _append_line(self, level: int, msg: str) -> None:
        color = self.LEVEL_COLORS.get(level, "#e8eaf6")
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(msg + "\n", fmt)

        # Auto-scroll
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())

    def limpar(self) -> None:
        self.clear()
