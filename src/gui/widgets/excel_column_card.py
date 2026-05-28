"""
ExcelColumnCard — card drop-target representando uma coluna/categoria do Excel.

Aceita drops de ApiAttrChip. Múltiplos atributos são acumulados (soma).
Cada atributo mapeado aparece como um badge com botão × de remoção.
"""
from __future__ import annotations

import json as _json
from typing import Callable

from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QFont, QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget, QInputDialog,
)

from src.gui.styles import COLORS
from src.gui.widgets.api_attr_chip import MIME_TYPE

class _AttrBadge(QWidget):
    """Badge removível exibido dentro do card após um drop."""

    removed = Signal(dict)  # emitido com o payload removido

    def __init__(self, payload: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._payload = payload
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        label = payload.get("label", payload.get("caminho_json", ""))
        display = label if len(label) <= 30 else label[:28] + "…"

        lbl = QLabel(display)
        lbl.setFont(QFont("Segoe UI", 9))
        lbl.setToolTip(label)

        self._btn_sinal = QPushButton()
        self._btn_sinal.setObjectName("badge_sinal")
        self._btn_sinal.setFixedSize(16, 16)
        self._btn_sinal.clicked.connect(self._alternar_sinal)
        self._atualizar_texto_sinal()

        btn_rm = QPushButton("×")
        btn_rm.setObjectName("badge_remove")
        btn_rm.setFixedSize(16, 16)
        btn_rm.clicked.connect(lambda: self.removed.emit(self._payload))

        layout.addWidget(lbl)
        layout.addWidget(self._btn_sinal)
        layout.addWidget(btn_rm)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['accent']}22;
                border: 1px solid {COLORS['accent']};
                border-radius: 10px;
                padding: 2px 4px;
            }}
            QLabel {{ color: {COLORS['text']}; background: transparent; border: none; padding: 0; }}
            QPushButton#badge_remove, QPushButton#badge_sinal {{
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: bold;
                padding: 0;
                margin: 0;
                min-width: 16px;
                min-height: 16px;
            }}
            QPushButton#badge_remove {{ color: {COLORS['text_muted']}; }}
            QPushButton#badge_remove:hover {{ color: {COLORS['error']}; }}
        """)

    def _alternar_sinal(self) -> None:
        atual = self._payload.get("multiplicador", 1.0)
        self._payload["multiplicador"] = -1.0 if atual == 1.0 else 1.0
        self._atualizar_texto_sinal()

    def _atualizar_texto_sinal(self) -> None:
        atual = self._payload.get("multiplicador", 1.0)
        if atual == -1.0:
            self._btn_sinal.setText("-")
            self._btn_sinal.setStyleSheet(f"color: {COLORS['error']};")
            self._btn_sinal.setToolTip("Invertendo sinal (Multiplicador: -1)")
        else:
            self._btn_sinal.setText("+")
            self._btn_sinal.setStyleSheet(f"color: {COLORS['success']};")
            self._btn_sinal.setToolTip("Sinal original (Multiplicador: 1)")


class ExcelColumnCard(QFrame):
    """
    Card drop target representando uma categoria do relatório Excel.

    Sinais:
        mapping_changed()  — emitido quando um atributo é adicionado ou removido
        delete_requested(card) — emitido quando o usuário solicita exclusão da coluna
    """

    mapping_changed = Signal()
    delete_requested = Signal(object)

    def __init__(
        self,
        categoria: str,
        atributos_iniciais: list[dict] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._categoria = categoria
        self._atributos: list[dict] = []  # lista de payloads mapeados

        self.setObjectName("excel_card")
        self.setAcceptDrops(True)
        self.setMinimumHeight(90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self._normal_style = f"""
            QFrame#excel_card {{
                background-color: {COLORS['surface']};
                border: 1.5px solid {COLORS['border']};
                border-radius: 10px;
                padding: 6px;
            }}
        """
        self._hover_style = f"""
            QFrame#excel_card {{
                background-color: {COLORS['surface_alt']};
                border: 2px dashed {COLORS['accent']};
                border-radius: 10px;
                padding: 6px;
            }}
        """
        self.setStyleSheet(self._normal_style)

        # --- Layout interno ---
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        # Cabeçalho
        header = QHBoxLayout()
        self._lbl_cat = QLabel(categoria)
        self._lbl_cat.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._lbl_cat.setStyleSheet(f"color: {COLORS['text']};")
        header.addWidget(self._lbl_cat)

        # Botões de edição e remoção do card/coluna
        self._btn_edit = QPushButton("Renomear")
        self._btn_edit.setToolTip("Renomear Coluna")
        self._btn_edit.setFixedHeight(22)
        self._btn_edit.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                color: {COLORS['text_muted']};
                font-family: 'Segoe UI';
                font-size: 10px;
                padding: 1px 6px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
                color: {COLORS['text']};
                background-color: {COLORS['surface_alt']};
            }}
        """)
        self._btn_edit.clicked.connect(self._renomear_coluna)
        header.addWidget(self._btn_edit)

        self._btn_delete = QPushButton("Excluir")
        self._btn_delete.setToolTip("Excluir Coluna do Mapeamento")
        self._btn_delete.setFixedHeight(22)
        self._btn_delete.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                color: {COLORS['text_muted']};
                font-family: 'Segoe UI';
                font-size: 10px;
                padding: 1px 6px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['error']};
                color: {COLORS['error']};
                background-color: {COLORS['surface_alt']};
            }}
        """)
        self._btn_delete.clicked.connect(lambda: self.delete_requested.emit(self))
        header.addWidget(self._btn_delete)

        header.addStretch()

        self._lbl_hint = QLabel("↓ arraste atributos aqui")
        self._lbl_hint.setFont(QFont("Segoe UI", 9))
        self._lbl_hint.setStyleSheet(f"color: {COLORS['text_muted']};")
        header.addWidget(self._lbl_hint)
        root.addLayout(header)

        # Área de badges
        self._badges_widget = QWidget()
        self._badges_widget.setStyleSheet("background: transparent;")
        self._badges_layout = QHBoxLayout(self._badges_widget)
        self._badges_layout.setContentsMargins(0, 0, 0, 0)
        self._badges_layout.setSpacing(4)
        self._badges_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        root.addWidget(self._badges_widget)

        # Carrega atributos iniciais (do JSON existente)
        for attr in (atributos_iniciais or []):
            self._adicionar_atributo_interno(attr, emit=False)

        self._atualizar_hint()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def categoria(self) -> str:
        return self._categoria

    def atributos_mapeados(self) -> list[dict]:
        return list(self._atributos)

    # ------------------------------------------------------------------
    # Drag & Drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(MIME_TYPE):
            event.acceptProposedAction()
            self.setStyleSheet(self._hover_style)
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasFormat(MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.setStyleSheet(self._normal_style)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setStyleSheet(self._normal_style)
        if event.mimeData().hasFormat(MIME_TYPE):
            raw = bytes(event.mimeData().data(MIME_TYPE)).decode("utf-8")
            payload = _json.loads(raw)
            self._adicionar_atributo_interno(payload, emit=True)
            event.acceptProposedAction()
        else:
            event.ignore()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _renomear_coluna(self) -> None:
        nome, ok = QInputDialog.getText(
            self, "Renomear Coluna", f"Novo nome para '{self._categoria}':",
            text=self._categoria
        )
        if ok and nome.strip() and nome.strip() != self._categoria:
            self._categoria = nome.strip()
            self._lbl_cat.setText(self._categoria)
            self.mapping_changed.emit()

    def _adicionar_atributo_interno(self, payload: dict, emit: bool = True) -> None:
        # Evita duplicatas pelo caminho_json + filtros
        key = (
            payload.get("caminho_json"),
            payload.get("chave_filtro_json"),
            payload.get("valor_filtro_json"),
            payload.get("campo_valor_json"),
        )
        existing_keys = [
            (
                a.get("caminho_json"),
                a.get("chave_filtro_json"),
                a.get("valor_filtro_json"),
                a.get("campo_valor_json"),
            )
            for a in self._atributos
        ]
        if key in existing_keys:
            return

        self._atributos.append(payload)

        badge = _AttrBadge(payload)
        badge.removed.connect(self._remover_atributo)
        self._badges_layout.addWidget(badge)
        self._atualizar_hint()

        if emit:
            self.mapping_changed.emit()

    def _remover_atributo(self, payload: dict) -> None:
        key = (
            payload.get("caminho_json"),
            payload.get("chave_filtro_json"),
            payload.get("valor_filtro_json"),
            payload.get("campo_valor_json"),
        )
        self._atributos = [
            a for a in self._atributos
            if (
                a.get("caminho_json"),
                a.get("chave_filtro_json"),
                a.get("valor_filtro_json"),
                a.get("campo_valor_json"),
            ) != key
        ]

        # Remove o badge correspondente do layout
        for i in range(self._badges_layout.count()):
            item = self._badges_layout.itemAt(i)
            if item and isinstance(item.widget(), _AttrBadge):
                w: _AttrBadge = item.widget()
                if w._payload.get("caminho_json") == payload.get("caminho_json") \
                   and w._payload.get("valor_filtro_json") == payload.get("valor_filtro_json"):
                    w.setParent(None)
                    w.deleteLater()
                    break

        self._atualizar_hint()
        self.mapping_changed.emit()

    def _atualizar_hint(self) -> None:
        tem = len(self._atributos) > 0
        self._lbl_hint.setVisible(not tem)
        if tem and len(self._atributos) > 1:
            self._lbl_hint.setText(f"∑ {len(self._atributos)} atributos somados")
            self._lbl_hint.setVisible(True)
            self._lbl_hint.setStyleSheet(f"color: {COLORS['success']}; font-size: 9px;")
