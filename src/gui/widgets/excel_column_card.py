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

        self._lbl = QLabel(display)
        self._lbl.setFont(QFont("Segoe UI", 9))
        self._lbl.setToolTip(self._tooltip(payload))

        self._btn_sinal = QPushButton()
        self._btn_sinal.setObjectName("badge_sinal")
        self._btn_sinal.setFixedSize(16, 16)
        self._btn_sinal.clicked.connect(self._alternar_sinal)
        self._atualizar_texto_sinal()

        btn_rm = QPushButton("×")
        btn_rm.setObjectName("badge_remove")
        btn_rm.setFixedSize(16, 16)
        btn_rm.clicked.connect(lambda: self.removed.emit(self._payload))

        layout.addWidget(self._lbl)
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

    def atualizar_payload(self, novo_payload: dict) -> None:
        """Atualiza o payload interno, o texto de exibição e o tooltip."""
        self._payload = novo_payload
        label = novo_payload.get("label", novo_payload.get("caminho_json", ""))
        display = label if len(label) <= 30 else label[:28] + "…"
        self._lbl.setText(display)
        self._lbl.setToolTip(self._tooltip(novo_payload))
        self._lbl.adjustSize()

    def _tooltip(self, payload: dict) -> str:
        label = payload.get("label", payload.get("caminho_json", ""))
        val = payload.get("valor_retornado")
        if val is None:
            val = payload.get("valor_exemplo")
            
        valor_str = "— (Nulo/Vazio)"
        if val is not None:
            try:
                val_num = float(val)
                valor_str = f"{val_num:,.2f}"
            except (ValueError, TypeError):
                valor_str = str(val)
                
        fonte = payload.get("fonte", "api_json")
        origem = "📍 Origem: Fixo / Outro"
        detalhes = ""
        if fonte == "api_json":
            origem = "🔌 Origem: API JSON"
            detalhes = f"<b>Caminho:</b> {payload.get('caminho_json')}"
        elif fonte == "valor_carteira":
            origem = "📁 Origem: Célula de Planilha"
            detalhes = f"<b>Linha:</b> {payload.get('chave_etl')}<br><b>Coluna:</b> {payload.get('coluna')}"
        elif fonte in ("atributo", "taxa"):
            origem = "⚙️ Origem: Atributo / Taxa"
            detalhes = f"<b>Nome Técnico:</b> {payload.get('campo')}"
        elif fonte == "cotas":
            origem = "📊 Origem: Bloco de Cotas"
            detalhes = f"<b>Ordem:</b> {payload.get('ordens')}<br><b>Métrica:</b> {payload.get('coluna_valor')}"
        elif fonte == "contas":
            origem = "🏦 Origem: Contas e Provisões"
            detalhes = f"<b>Filtro:</b> {payload.get('filtro')}"
        elif fonte == "soma_secao":
            origem = "🧮 Origem: Soma Seção"
            detalhes = f"<b>Seção:</b> {payload.get('secao')}<br><b>Coluna:</b> {payload.get('coluna')}"
            
        html = f"""
        <div style="font-family: 'Segoe UI'; font-size: 11px; margin: 4px;">
            <div style="font-weight: bold; color: #3182ce; font-size: 12px; margin-bottom: 4px;">{label}</div>
            <div style="color: #a0aec0; margin-bottom: 6px;">{origem}</div>
            {f'<div style="color: #cbd5e0; margin-bottom: 6px; line-height: 1.3;">{detalhes}</div>' if detalhes else ''}
            <div style="border-top: 1px solid #4a5568; padding-top: 4px; margin-top: 6px;">
                <span style="color: #cbd5e0;">Valor Mapeado:</span> 
                <span style="font-size: 12px; color: #f6ad55; font-weight: bold;">{valor_str}</span>
            </div>
        </div>
        """
        return html

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
def _obter_chave_payload(payload: dict) -> tuple:
    fonte = payload.get("fonte", "api_json")
    if fonte == "api_json":
        return (
            "api_json",
            payload.get("caminho_json"),
            payload.get("chave_filtro_json"),
            payload.get("valor_filtro_json"),
            payload.get("campo_valor_json"),
        )
    elif fonte in ("atributo", "taxa"):
        return (fonte, payload.get("campo"))
    elif fonte == "valor_carteira":
        return ("valor_carteira", payload.get("chave_etl"), payload.get("coluna"))
    elif fonte == "cotas":
        ordens = payload.get("ordens")
        ordens_tuple = tuple(ordens) if ordens else ()
        return ("cotas", ordens_tuple, payload.get("coluna_valor"))
    elif fonte == "contas":
        return ("contas", payload.get("filtro"), payload.get("dataframe"))
    elif fonte == "fixo":
        return ("fixo", payload.get("valor_fixo"))
    elif fonte == "custom":
        return ("custom", payload.get("nome_funcao"))
    elif fonte == "soma_secao":
        return ("soma_secao", payload.get("secao"), payload.get("coluna"))
    return (fonte, payload.get("label"))


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

    def atualizar_variaveis_carregadas(self, variaveis: list[dict]) -> None:
        """
        Dadas as variáveis realmente detectadas e carregadas do arquivo físico,
        mescla seus rótulos reais e valores retornados nos badges deste card.
        Útil para substituir 'Col 5' por 'Valor Total' após carregar o arquivo Excel.
        """
        vars_map = {_obter_chave_payload(v): v for v in variaveis}
        
        # Percorre as variáveis internas mapeadas e atualiza o payload
        novos_atributos = []
        for attr in self._atributos:
            key = _obter_chave_payload(attr)
            if key in vars_map:
                novo_p = dict(attr)
                novo_p.update(vars_map[key])
                novos_atributos.append(novo_p)
            else:
                novos_atributos.append(attr)
        self._atributos = novos_atributos

        # Percorre os widgets de badges do layout e atualiza-os visualmente
        for i in range(self._badges_layout.count()):
            item = self._badges_layout.itemAt(i)
            if item and isinstance(item.widget(), _AttrBadge):
                badge: _AttrBadge = item.widget()
                key = _obter_chave_payload(badge._payload)
                if key in vars_map:
                    novo_p = dict(badge._payload)
                    novo_p.update(vars_map[key])
                    badge.atualizar_payload(novo_p)

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
        # Evita duplicatas usando chave universal
        key = _obter_chave_payload(payload)
        existing_keys = [_obter_chave_payload(a) for a in self._atributos]
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
        key = _obter_chave_payload(payload)
        self._atributos = [
            a for a in self._atributos
            if _obter_chave_payload(a) != key
        ]

        # Remove o badge correspondente do layout
        for i in range(self._badges_layout.count()):
            item = self._badges_layout.itemAt(i)
            if item and isinstance(item.widget(), _AttrBadge):
                w: _AttrBadge = item.widget()
                if _obter_chave_payload(w._payload) == key:
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
