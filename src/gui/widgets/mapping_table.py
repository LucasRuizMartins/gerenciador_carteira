"""
MappingTable — QTableWidget editável para os itens de mapeamento JSON.
Suporta validação inline, ComboBox para coluna "fonte" e
highlight de linhas modificadas.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

# Colunas visíveis e suas larguras relativas
COLUNAS = [
    ("Coluna Excel (Categoria)", 250, True),
    ("Fonte (Regra)",           140, False),
    ("Filtro",                  180, True),
    ("Origem (DF)",              110, False),
    ("Campo / Valor / Chave",   180, True),
    ("Coluna / Ordens #",        90, True),
    ("Multiplicador",            80, True),
]

DFS = ["Despesas", "Recebíveis"]
MAP_DFS = {
    "Despesas": "df_contas_filtrado",
    "Recebíveis": "df_contas_receber_filtrado"
}
INV_MAP_DFS = {v: k for k, v in MAP_DFS.items()}

FONTES = [
    "atributo", "taxa", "fixo", "custom",
    "valor_carteira", "cotas", "contas",
]

_COLOR_MODIFIED = QColor("#f0a50030")   # amarelo translúcido
_COLOR_ERROR    = QColor("#f0525230")   # vermelho translúcido
_COLOR_NORMAL   = QColor("transparent")





class MappingTable(QTableWidget):
    """
    Tabela editável para itens de mapeamento CD ou MEC.

    Uso:
        table = MappingTable(parent)
        table.carregar(lista_itens)
        dados = table.exportar()
    """

    modificado = Signal()  # emitido quando qualquer célula muda

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._linhas_modificadas: set[int] = set()
        self._configurar()

    def _configurar(self) -> None:
        self.setColumnCount(len(COLUNAS))
        self.setHorizontalHeaderLabels([c[0] for c in COLUNAS])
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(False)
        self.verticalHeader().setDefaultSectionSize(40)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(True)

        # Tooltips explicativos
        tips = [
            "Nome exato da linha no relatório Excel (CD ou MEC).",
            "Como o robô deve buscar o valor: Atributo, Contas (planilha), Fixo, etc.",
            "Texto para procurar na coluna 'Histórico' da planilha (use quando Fonte for 'contas').",
            "Qual gaveta de dados usar: Despesas (contas a pagar) ou Recebíveis (diferimentos).",
            "Detalhe técnico: nome da variável (atributo), valor numérico (fixo) ou nome do ativo.",
            "Índice da coluna Excel (valor_carteira) ou lista de ordens [1,2,3] (cotas).",
            "Multiplicador (ex: -1 para inverter o sinal)."
        ]

        hh = self.horizontalHeader()
        for i, tip in enumerate(tips):
            if i < len(COLUNAS):
                self.model().setHeaderData(i, Qt.Orientation.Horizontal, tip, Qt.ItemDataRole.ToolTipRole)

        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, (_, width, _) in enumerate(COLUNAS[1:], 1):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            self.setColumnWidth(i, width)

        self.itemChanged.connect(self._on_item_changed)

    # ------------------------------------------------------------------
    # Carregamento / Exportação
    # ------------------------------------------------------------------

    def carregar(self, itens: list[dict]) -> None:
        """Popula a tabela com a lista de itens de mapeamento."""
        self.itemChanged.disconnect(self._on_item_changed)
        self.setRowCount(0)
        self._linhas_modificadas.clear()

        for item in itens:
            self._inserir_linha(item)

        self.itemChanged.connect(self._on_item_changed)

    def _inserir_linha(self, item: dict, row: int | None = None) -> None:
        if row is None:
            row = self.rowCount()
        self.insertRow(row)

        def _cell(val: str) -> QTableWidgetItem:
            cell = QTableWidgetItem(str(val) if val is not None else "")
            return cell

        self.setItem(row, 0, _cell(item.get("categoria", "")))

        # Fonte: ComboBox direto (sem delegate para evitar bugs de layout)
        combo = QComboBox()
        combo.addItems(FONTES)
        fonte_atual = item.get("fonte", "atributo")
        idx = combo.findText(fonte_atual)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        
        # Estilo forçado para garantir legibilidade
        combo.setMinimumWidth(130)
        combo.setStyleSheet("font-size: 13px; color: white; background-color: #242840;")
        combo.currentTextChanged.connect(lambda _, r=row: self._marcar_modificada(r))
        self.setCellWidget(row, 1, combo)

        # Campo / chave / valor (tenta encontrar qualquer valor preenchido no JSON)
        chave = (
            item.get("campo") or
            item.get("nome_funcao") or
            item.get("chave_etl") or
            item.get("coluna_valor") or
            item.get("filtro") or
            str(item.get("valor_fixo", ""))
        )
        
        # Coluna / Ordens (tenta encontrar coluna ou lista de ordens)
        col_val = item.get("coluna")
        if col_val is None and item.get("ordens"):
            col_val = ", ".join(map(str, item.get("ordens")))

        self.setItem(row, 2, _cell(item.get("filtro", "")))
        
        # Origem DF: ComboBox para Contas a Pagar/Receber
        combo_df = QComboBox()
        combo_df.addItems(DFS)
        df_atual = item.get("dataframe") or "df_contas_filtrado"
        texto_df = INV_MAP_DFS.get(df_atual, "Despesas")
        idx_df = combo_df.findText(texto_df)
        combo_df.setCurrentIndex(idx_df if idx_df >= 0 else 0)
        combo_df.setStyleSheet("font-size: 12px;")
        combo_df.currentTextChanged.connect(lambda _, r=row: self._marcar_modificada(r))
        self.setCellWidget(row, 3, combo_df)

        self.setItem(row, 4, _cell(chave))
        self.setItem(row, 5, _cell(col_val if col_val is not None else ""))
        self.setItem(row, 6, _cell(item.get("multiplicador", "")))

    def exportar(self) -> list[dict]:
        """Converte o estado atual da tabela em lista de dicts JSON."""
        resultado = []
        for row in range(self.rowCount()):
            combo = self.cellWidget(row, 1)
            fonte = combo.currentText() if isinstance(combo, QComboBox) else "atributo"

            cat  = self._text(row, 0)
            filt  = self._text(row, 2)
            
            c_df  = self.cellWidget(row, 3)
            origem = c_df.currentText() if isinstance(c_df, QComboBox) else "Despesas"
            df_name = MAP_DFS.get(origem, "df_contas_filtrado")

            campo = self._text(row, 4)
            col   = self._text(row, 5)
            mult  = self._text(row, 6)

            item: dict = {"categoria": cat, "fonte": fonte}

            # Mapeia campo conforme tipo de fonte
            if fonte == "atributo":
                item["campo"] = campo
            elif fonte == "taxa":
                item["campo"] = campo
            elif fonte == "fixo":
                try:
                    item["valor_fixo"] = float(campo) if campo else 0
                except ValueError:
                    item["valor_fixo"] = campo
            elif fonte == "custom":
                item["nome_funcao"] = campo
            elif fonte == "valor_carteira":
                item["chave_etl"] = campo
                if col:
                    try: item["coluna"] = int(col)
                    except ValueError: pass
            elif fonte == "cotas":
                item["coluna_valor"] = campo
                if col:
                    try: item["ordens"] = [int(c.strip()) for c in col.split(",")]
                    except ValueError: pass
            elif fonte == "contas":
                item["filtro"] = filt or campo
                item["dataframe"] = df_name

            if mult:
                try: item["multiplicador"] = float(mult)
                except ValueError: pass

            resultado.append(item)
        return resultado

    def _text(self, row: int, col: int) -> str:
        cell = self.item(row, col)
        return cell.text().strip() if cell else ""

    # ------------------------------------------------------------------
    # Manipulação de linhas
    # ------------------------------------------------------------------

    def adicionar_linha(self) -> None:
        row = self.rowCount()
        self._inserir_linha(
            {"categoria": "Nova Categoria", "fonte": "fixo", "valor_fixo": 0},
            row
        )
        self._marcar_modificada(row)
        self.scrollToBottom()
        self.selectRow(row)

    def remover_linha_selecionada(self) -> None:
        rows = sorted({i.row() for i in self.selectedItems()}, reverse=True)
        for r in rows:
            self.removeRow(r)
        self.modificado.emit()

    def mover_linha(self, direcao: int) -> None:
        """direcao: -1 para cima, +1 para baixo."""
        rows = sorted({i.row() for i in self.selectedItems()})
        if not rows:
            return
        row = rows[0]
        target = row + direcao
        if target < 0 or target >= self.rowCount():
            return

        # Salva dados de ambas as linhas
        def _extrair(r: int) -> tuple:
            combo = self.cellWidget(r, 1)
            fonte = combo.currentText() if isinstance(combo, QComboBox) else "atributo"
            return (
                self._text(r, 0), fonte,
                self._text(r, 2), self._text(r, 3),
                self._text(r, 4), self._text(r, 5),
            )

        dados_row    = _extrair(row)
        dados_target = _extrair(target)

        def _preencher(r: int, dados: tuple) -> None:
            cat, fonte, campo, col, mult, filt = dados
            self.item(r, 0).setText(cat)
            combo = self.cellWidget(r, 1)
            if isinstance(combo, QComboBox):
                idx = combo.findText(fonte)
                combo.setCurrentIndex(idx if idx >= 0 else 0)
            for c, val in [(2, campo), (3, col), (4, mult), (5, filt)]:
                if self.item(r, c):
                    self.item(r, c).setText(val)
                else:
                    self.setItem(r, c, QTableWidgetItem(val))

        _preencher(row, dados_target)
        _preencher(target, dados_row)
        self.selectRow(target)

    # ------------------------------------------------------------------
    # Validação inline
    # ------------------------------------------------------------------

    def validar_visual(self) -> bool:
        """Pinta células inválidas de vermelho. Retorna True se tudo OK."""
        ok = True
        for row in range(self.rowCount()):
            cat = self._text(row, 0)
            is_ok = bool(cat)
            cor = _COLOR_NORMAL if is_ok else _COLOR_ERROR
            if not is_ok:
                ok = False
            for col in range(self.columnCount()):
                cell = self.item(row, col)
                if cell:
                    cell.setBackground(QBrush(cor))
        return ok

    # ------------------------------------------------------------------
    # Slots internos
    # ------------------------------------------------------------------

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        self._marcar_modificada(item.row())

    def _marcar_modificada(self, row: int) -> None:
        self._linhas_modificadas.add(row)
        for col in range(self.columnCount()):
            cell = self.item(row, col)
            if cell:
                cell.setBackground(QBrush(_COLOR_MODIFIED))
        self.modificado.emit()
