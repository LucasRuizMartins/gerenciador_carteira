"""
ApiAttrChip — chip arrastável representando um atributo do JSON da API.

Estados visuais:
  novo      → vermelho   — detectado na API, sem mapeamento
  mapeado   → verde      — já associado a uma coluna do Excel
  livre     → amarelo    — conhecido mas ainda não associado
"""
from __future__ import annotations

import json as _json
from PySide6.QtCore import Qt, QMimeData, QPoint, QSize
from PySide6.QtGui import QDrag, QFont, QMouseEvent, QPixmap, QPainter, QColor
from PySide6.QtWidgets import QLabel, QWidget

from src.gui.styles import COLORS

MIME_TYPE = "application/x-api-attr"

_STATUS_STYLES = {
    "novo": {
        "bg":     "#4a1a2a",
        "border": "#f05252",
        "text":   "#f05252",
        "dot":    "#f05252",
    },
    "livre": {
        "bg":     "#3a3010",
        "border": "#f0a500",
        "text":   "#f0a500",
        "dot":    "#f0a500",
    },
    "mapeado": {
        "bg":     "#0d2a1a",
        "border": "#4caf82",
        "text":   "#4caf82",
        "dot":    "#4caf82",
    },
}


class ApiAttrChip(QLabel):
    """
    Chip drag-able para um atributo JSON da API.

    payload_dict: {
        "caminho_json":      str,           # ex: "posicaoCaixa.total.totalValorTotal"
        "chave_filtro_json": str | None,    # ex: "papel"
        "valor_filtro_json": str | None,    # ex: "A VENCER"
        "campo_valor_json":  str | None,    # ex: "valorPresente"
        "label":             str,           # texto exibido no chip
    }
    status: "novo" | "livre" | "mapeado"
    """

    def __init__(
        self,
        payload: dict,
        status: str = "livre",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._payload = payload
        self._status = status
        self._drag_start: QPoint | None = None

        self._render()
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(self._tooltip())

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def payload(self) -> dict:
        return self._payload

    @property
    def status(self) -> str:
        return self._status

    def set_status(self, status: str) -> None:
        self._status = status
        self._render()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> None:
        st = _STATUS_STYLES.get(self._status, _STATUS_STYLES["livre"])
        label = self._payload.get("label_curto") or self._payload.get("label", self._payload.get("caminho_json", ""))
        # Trunca rótulo longo
        display = label if len(label) <= 38 else label[:36] + "…"
        self.setText(f"  ● {display}  ")
        self.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {st['bg']};
                border: 1px solid {st['border']};
                border-radius: 12px;
                color: {st['text']};
                padding: 2px 10px;
                margin: 0px;
            }}
            QLabel:hover {{
                background-color: {st['border']}33;
            }}
        """)
        self.setFixedHeight(28)
        self.adjustSize()

    def _tooltip(self) -> str:
        p = self._payload
        lines = [f"Caminho: {p.get('caminho_json', '')}"]
        if p.get("chave_filtro_json"):
            lines.append(f"Filtro: {p['chave_filtro_json']} = {p.get('valor_filtro_json', '')}")
        if p.get("campo_valor_json"):
            lines.append(f"Campo valor: {p['campo_valor_json']}")

        # Adiciona o valor retornado de forma destacada e formatada
        val = p.get("valor_retornado")
        if val is not None:
            if isinstance(val, float):
                # Se for float, formata como decimal elegante
                lines.append(f"Valor retornado: {val:,.4f}")
            elif isinstance(val, (int, float)):
                lines.append(f"Valor retornado: {val:,}")
            else:
                lines.append(f"Valor retornado: {val}")
        else:
            lines.append("Valor retornado: — (Vazio/Nulo)")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Drag support
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._drag_start is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            delta = (event.position().toPoint() - self._drag_start).manhattanLength()
            if delta >= 8:
                self._iniciar_drag()
        super().mouseMoveEvent(event)

    def _iniciar_drag(self) -> None:
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

        mime = QMimeData()
        mime.setData(MIME_TYPE, _json.dumps(self._payload).encode("utf-8"))

        # Cria pixmap de preview
        pm = self.grab()

        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(pm)
        drag.setHotSpot(QPoint(pm.width() // 2, pm.height() // 2))
        drag.exec(Qt.DropAction.CopyAction)

        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._drag_start = None
