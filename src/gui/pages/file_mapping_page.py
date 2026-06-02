"""
FileMappingPage — interface drag-and-drop para mapeamento de atributos locais (CSV/XLSX)
para colunas do relatório Excel.

Layout:
    [Seletor de fundo + botão carregar]
    ─────────────────────────────────────────────
    [Painel Variáveis Arquivo]  |  [Painel Colunas Excel]
    ─────────────────────────────────────────────
    [status bar + botão salvar]
"""
from __future__ import annotations

import json as _json
from datetime import date

from PySide6.QtCore import Qt, QSize, QPoint, QMimeData
from PySide6.QtGui import QFont, QColor, QShowEvent, QMouseEvent, QDrag, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QInputDialog,
    QLabel, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSplitter, QTabWidget, QVBoxLayout, QWidget,
    QTreeWidget, QTreeWidgetItem, QLineEdit,
)

from src.gui.styles import COLORS
from src.gui.viewmodels.file_mapping_vm import FileMappingViewModel
from src.gui.widgets.excel_column_card import ExcelColumnCard
from src.gui.widgets.api_attr_chip import MIME_TYPE, _STATUS_STYLES


class FileAttrChip(QLabel):
    """
    Chip drag-able para variáveis de arquivos locais (CSV/XLSX).
    Usa o mesmo MIME_TYPE que ApiAttrChip para permitir drop no ExcelColumnCard.
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

    @property
    def payload(self) -> dict:
        return self._payload

    @property
    def status(self) -> str:
        return self._status

    def set_status(self, status: str) -> None:
        self._status = status
        self._render()

    def _render(self) -> None:
        st = _STATUS_STYLES.get(self._status, _STATUS_STYLES["livre"])
        label = self._payload.get("label_curto") or self._payload.get("label", "")
        # Trunca rótulo longo
        display = label if len(label) <= 45 else label[:42] + "…"
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
        fonte = p.get("fonte", "fixo")
        val = p.get("valor_retornado")
        
        origem = "📍 Origem: Fixo / Outro"
        detalhes = ""
        if fonte == "valor_carteira":
            origem = "📁 Origem: Célula de Planilha"
            detalhes = f"<b>Linha:</b> {p.get('chave_etl')}<br><b>Coluna:</b> {p.get('coluna')}"
        elif fonte in ("atributo", "taxa"):
            tipo = "Atributo Financeiro" if fonte == "atributo" else "Taxa/Despesa"
            origem = f"⚙️ Origem: {tipo}"
            detalhes = f"<b>Nome Técnico:</b> {p.get('campo')}"
        elif fonte == "cotas":
            origem = "📊 Origem: Bloco de Cotas"
            detalhes = f"<b>Ordem da Cota:</b> {p.get('ordens')}<br><b>Métrica:</b> {p.get('coluna_valor')}"
        elif fonte == "contas":
            df_label = "Despesas (a Pagar)" if p.get("dataframe") == "df_contas_filtrado" else "Recebíveis (a Receber)"
            origem = "🏦 Origem: Contas e Provisões"
            detalhes = f"<b>Filtro:</b> {p.get('filtro')}<br><b>Grupo:</b> {df_label}"
            
        valor_str = "— (Nulo/Vazio)"
        if val is not None:
            try:
                val_num = float(val)
                valor_str = f"{val_num:,.2f}"
            except (ValueError, TypeError):
                valor_str = str(val)
                
        html = f"""
        <div style="font-family: 'Segoe UI'; font-size: 11px; margin: 4px;">
            <div style="font-weight: bold; color: #4caf82; font-size: 12px; margin-bottom: 4px;">{p.get('label', '')}</div>
            <div style="color: #a0aec0; margin-bottom: 6px;">{origem}</div>
            {f'<div style="color: #cbd5e0; margin-bottom: 6px; line-height: 1.3;">{detalhes}</div>' if detalhes else ''}
            <div style="border-top: 1px solid #4a5568; padding-top: 4px; margin-top: 6px;">
                <span style="color: #cbd5e0;">Valor Detectado:</span> 
                <span style="font-size: 12px; color: #f6ad55; font-weight: bold;">{valor_str}</span>
            </div>
        </div>
        """
        return html

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

        pm = self.grab()

        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(pm)
        drag.setHotSpot(QPoint(pm.width() // 2, pm.height() // 2))
        drag.exec(Qt.DropAction.CopyAction)

        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._drag_start = None


class _ChipPanel(QWidget):
    """Painel esquerdo: exibe as variáveis do portfólio organizadas por categorias."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        lbl = QLabel("Variáveis Detectadas no Portfólio")
        lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {COLORS['text']};")
        root.addWidget(lbl)

        legenda = QHBoxLayout()
        for cor, txt in [("#f05252", "Novo"), ("#f0a500", "Não mapeado"), ("#4caf82", "Mapeado")]:
            dot = QLabel(f"● {txt}")
            dot.setFont(QFont("Segoe UI", 9))
            dot.setStyleSheet(f"color: {cor};")
            legenda.addWidget(dot)
        legenda.addStretch()
        root.addLayout(legenda)

        # Barra de Pesquisa de Variáveis
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 Filtrar variáveis por nome ou campo...")
        self._search_input.setFixedHeight(30)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                color: {COLORS['text']};
                padding: 4px 10px;
                font-family: 'Segoe UI';
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """)
        self._search_input.textChanged.connect(self._filtrar_variaveis)
        root.addWidget(self._search_input)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(18)
        self._tree.setAnimated(True)
        self._tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 6px;
            }}
            QTreeWidget::item {{
                padding: 6px 2px;
                background-color: transparent;
                border: none;
            }}
            QTreeWidget::item:hover {{
                background-color: transparent;
            }}
        """)
        root.addWidget(self._tree)

        self._chips: dict[str, FileAttrChip] = {}

    def carregar(self, variaveis: list[dict], status_map: dict[str, str]) -> None:
        """Recria a árvore agrupando as variáveis por grupo/categoria."""
        self._search_input.blockSignals(True)
        self._search_input.clear()
        self._search_input.blockSignals(False)

        self._tree.clear()
        self._chips.clear()

        # Cache de nós/pastas principais
        pastas_cache: dict[str, QTreeWidgetItem] = {}

        def obter_pasta(nome_pasta: str, icone: str) -> QTreeWidgetItem:
            if nome_pasta not in pastas_cache:
                item = QTreeWidgetItem(self._tree.invisibleRootItem())
                item.setText(0, f"{icone} {nome_pasta}")
                item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
                item.setForeground(0, QColor(COLORS["accent_hover"]))
                pastas_cache[nome_pasta] = item
            return pastas_cache[nome_pasta]

        for var in variaveis:
            grupo = var.get("grupo", "Outros")
            label = var.get("label", "")
            status = status_map.get(label, "livre")

            # Resolve a pasta correspondente
            if grupo == "Atributos":
                parent_item = obter_pasta("Atributos do Fundo", "⚙️")
                nome_folha = label
            elif grupo == "Taxas":
                parent_item = obter_pasta("Taxas da Carteira", "💵")
                nome_folha = label
            elif grupo == "Cotas" or grupo.startswith("Cotas"):
                parent_item = obter_pasta("Cotas Superiores", "📊")
                nome_folha = label
            elif grupo in ("Contas a Pagar", "Contas a Receber"):
                parent_item = obter_pasta("Contas e Provisões", "🏦")
                nome_folha = label
            elif grupo.startswith("Planilha:"):
                # Agrupa linhas de planilha como subpastas de um nó raiz
                raiz_planilha = obter_pasta("Linhas e Células (Browse do CSV/XLSX)", "📂")
                nome_linha = grupo.replace("Planilha: ", "")
                
                # Cria subpasta para a linha específica da planilha
                chave_sub = f"plan_{nome_linha}"
                if chave_sub not in pastas_cache:
                    sub = QTreeWidgetItem(raiz_planilha)
                    sub.setText(0, f"📄 Linha: {nome_linha}")
                    sub.setFont(0, QFont("Segoe UI", 9, QFont.Weight.Bold))
                    sub.setForeground(0, QColor(COLORS["text_muted"]))
                    pastas_cache[chave_sub] = sub
                
                parent_item = pastas_cache[chave_sub]
                nome_folha = label.replace(f"{nome_linha} ", "")
            else:
                parent_item = obter_pasta("Outros", "📍")
                nome_folha = label

            # Adiciona o item contendo o chip arrastável
            folha_item = QTreeWidgetItem(parent_item)
            folha_item.setSizeHint(0, QSize(220, 36))

            chip_payload = dict(var)
            chip_payload["label_curto"] = nome_folha

            chip = FileAttrChip(chip_payload, status=status)
            chip.setMinimumWidth(180)

            self._tree.setItemWidget(folha_item, 0, chip)
            self._chips[label] = chip

    def atualizar_status(self, label: str, status: str) -> None:
        if label in self._chips:
            self._chips[label].set_status(status)

    def _filtrar_variaveis(self, texto: str) -> None:
        texto = texto.strip().lower()
        
        for i in range(self._tree.topLevelItemCount()):
            pasta = self._tree.topLevelItem(i)
            pasta_tem_visivel = False
            
            for j in range(pasta.childCount()):
                filho = pasta.child(j)
                
                if filho.childCount() > 0:
                    subpasta_tem_visivel = False
                    for k in range(filho.childCount()):
                        neto = child = filho.child(k)
                        widget = self._tree.itemWidget(neto, 0)
                        if isinstance(widget, FileAttrChip):
                            label_texto = widget.payload.get("label", "").lower()
                            campo_texto = widget.payload.get("campo", "").lower() if widget.payload.get("campo") else ""
                            match = (not texto) or (texto in label_texto) or (texto in campo_texto)
                            neto.setHidden(not match)
                            if match:
                                subpasta_tem_visivel = True
                    
                    filho.setHidden(not subpasta_tem_visivel)
                    if subpasta_tem_visivel:
                        pasta_tem_visivel = True
                        filho.setExpanded(bool(texto))
                else:
                    widget = self._tree.itemWidget(filho, 0)
                    if isinstance(widget, FileAttrChip):
                        label_texto = widget.payload.get("label", "").lower()
                        campo_texto = widget.payload.get("campo", "").lower() if widget.payload.get("campo") else ""
                        match = (not texto) or (texto in label_texto) or (texto in campo_texto)
                        filho.setHidden(not match)
                        if match:
                            pasta_tem_visivel = True
            
            pasta.setHidden(not pasta_tem_visivel)
            pasta.setExpanded(bool(texto))


class _CardPanel(QWidget):
    """Painel direito: exibe os cards drop-target das colunas do Excel (CD / MEC)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._changed_callback = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header = QHBoxLayout()
        lbl = QLabel("Colunas do Relatório Excel")
        lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {COLORS['text']};")
        header.addWidget(lbl)
        header.addStretch()

        self._btn_add = QPushButton("+ Nova Coluna")
        self._btn_add.setObjectName("btn_ghost")
        self._btn_add.setFixedHeight(30)
        self._btn_add.clicked.connect(self._adicionar_coluna)
        header.addWidget(self._btn_add)
        root.addLayout(header)

        # Barra de Pesquisa de Cards
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 Filtrar colunas do Excel por nome ou badges...")
        self._search_input.setFixedHeight(30)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                color: {COLORS['text']};
                padding: 4px 10px;
                font-family: 'Segoe UI';
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """)
        self._search_input.textChanged.connect(self._filtrar_cards)
        root.addWidget(self._search_input)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: 1px solid {COLORS['border']};
                border-radius: 10px; }}
        """)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._container)
        self._cards_layout.setContentsMargins(10, 10, 10, 10)
        self._cards_layout.setSpacing(8)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._container)
        root.addWidget(scroll)

        self._cards: list[ExcelColumnCard] = []

    def carregar(self, categorias: list[tuple[str, list[dict]]], changed_callback=None) -> None:
        self._changed_callback = changed_callback
        self._search_input.blockSignals(True)
        self._search_input.clear()
        self._search_input.blockSignals(False)

        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        for cat, payloads in categorias:
            self._criar_card(cat, payloads)

    def _criar_card(self, categoria: str, payloads: list[dict]) -> None:
        card = ExcelColumnCard(categoria, payloads)
        if self._changed_callback:
            card.mapping_changed.connect(self._changed_callback)
        card.delete_requested.connect(self._on_card_delete_requested)
        self._cards_layout.addWidget(card)
        self._cards.append(card)

    def _on_card_delete_requested(self, card: ExcelColumnCard) -> None:
        resp = QMessageBox.question(
            self,
            "Excluir Coluna",
            f"Deseja excluir a coluna '{card.categoria}' do mapeamento?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            self._cards.remove(card)
            card.setParent(None)
            card.deleteLater()
            if self._changed_callback:
                self._changed_callback()

    def _adicionar_coluna(self) -> None:
        nome, ok = QInputDialog.getText(
            self, "Nova Coluna", "Nome da categoria no Excel:"
        )
        if ok and nome.strip():
            self._criar_card(nome.strip(), [])
            if self._changed_callback:
                self._changed_callback()

    def cards(self) -> list[ExcelColumnCard]:
        return list(self._cards)

    def _filtrar_cards(self, texto: str) -> None:
        texto = texto.strip().lower()
        for card in self._cards:
            cat = card.categoria.lower()
            match = (not texto) or (texto in cat)
            
            if not match:
                for attr in card.atributos_mapeados():
                    label = attr.get("label", "").lower()
                    campo = attr.get("campo", "").lower() if attr.get("campo") else ""
                    secao = attr.get("secao", "").lower() if attr.get("secao") else ""
                    if (texto in label) or (texto in campo) or (texto in secao):
                        match = True
                        break
            
            card.setHidden(not match)


class FileMappingPage(QWidget):
    """
    Página principal de mapeamento visual de Arquivos Locais (CSV/XLSX) → Excel.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = FileMappingViewModel(self)
        self._fundo_atual: str | None = None
        self._variaveis: list[dict] = []

        self._setup_ui()
        self._conectar_vm()
        self._popular_fundos()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)

        # Cabeçalho
        title = QLabel("Mapeamento Visual de Arquivos (CSV/XLSX)")
        title.setObjectName("page_title")
        subtitle = QLabel(
            "Arraste as variáveis extraídas da planilha ou taxas calculadas para as colunas correspondentes "
            "do relatório gerencial Excel. Múltiplas regras na mesma categoria acumulam os valores automaticamente."
        )
        subtitle.setObjectName("page_subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        # Barra de Controles
        ctrl = QFrame()
        ctrl.setStyleSheet(
            f"background-color: {COLORS['surface']}; border-radius: 8px;"
        )
        ctrl_layout = QHBoxLayout(ctrl)
        ctrl_layout.setContentsMargins(16, 12, 16, 12)
        ctrl_layout.setSpacing(12)

        # Seletor de Fundo
        self._cb_fundo = QComboBox()
        self._cb_fundo.setFixedHeight(36)
        self._cb_fundo.setMinimumWidth(180)
        self._cb_fundo.currentTextChanged.connect(self._on_fundo_changed)
        ctrl_layout.addWidget(QLabel("Fundo:"))
        ctrl_layout.addWidget(self._cb_fundo)

        # Caminho do Arquivo
        self._lbl_caminho = QLabel("")
        self._lbl_caminho.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-family: Consolas;")
        self._lbl_caminho.setWordWrap(True)
        ctrl_layout.addWidget(self._lbl_caminho)

        ctrl_layout.addStretch()

        # Botão Consultar / Carregar Arquivo
        self._btn_query = QPushButton("📂 Carregar Arquivo")
        self._btn_query.setFixedHeight(36)
        self._btn_query.setEnabled(False)
        self._btn_query.clicked.connect(self._on_carregar_arquivo)
        ctrl_layout.addWidget(self._btn_query)

        root.addWidget(ctrl)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # Splitter principal: variáveis | cards
        self._tabs = QTabWidget()
        self._tab_cd  = self._criar_aba_split()
        self._tab_mec = self._criar_aba_split()
        self._tabs.addTab(self._tab_cd,  "📋 CD (Carteira Diária)")
        self._tabs.addTab(self._tab_mec, "📊 MEC (Mecânico)")
        root.addWidget(self._tabs)

        # Barra inferior: status + salvar
        bottom = QHBoxLayout()
        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        bottom.addWidget(self._lbl_status)
        bottom.addStretch()

        self._btn_save = QPushButton("💾 Salvar Mapeamento")
        self._btn_save.setFixedHeight(38)
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_salvar)
        bottom.addWidget(self._btn_save)
        root.addLayout(bottom)

    def _criar_aba_split(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        chips = _ChipPanel()
        cards = _CardPanel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(chips)
        splitter.addWidget(cards)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)

        layout.addWidget(splitter)

        w._chip_panel = chips
        w._card_panel = cards
        return w

    def _conectar_vm(self) -> None:
        self._vm.variaveis_prontas.connect(self._on_variaveis_prontas)
        self._vm.mapeamento_carregado.connect(self._on_mapeamento_carregado)
        self._vm.salvo.connect(self._on_salvo)
        self._vm.erro.connect(self._on_erro)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._popular_fundos()

    def _popular_fundos(self) -> None:
        atual = self._cb_fundo.currentText()
        self._cb_fundo.blockSignals(True)
        self._cb_fundo.clear()

        fundos = self._vm.todos_os_fundos()
        if fundos:
            self._cb_fundo.addItems(fundos)
            self._cb_fundo.setEnabled(True)
            self._btn_query.setEnabled(True)
            
            idx = self._cb_fundo.findText(atual)
            if idx >= 0:
                self._cb_fundo.setCurrentIndex(idx)
        else:
            self._cb_fundo.addItem("Nenhum fundo cadastrado")
            self._cb_fundo.setEnabled(False)
            self._btn_query.setEnabled(False)
            
        self._cb_fundo.blockSignals(False)

        if self._cb_fundo.currentText() != atual:
            self._on_fundo_changed(self._cb_fundo.currentText())

    def _on_fundo_changed(self, fundo: str) -> None:
        if not fundo or fundo == "Nenhum fundo cadastrado":
            self._lbl_caminho.setText("")
            return
        self._fundo_atual = fundo
        self._btn_save.setEnabled(False)
        self._lbl_status.setText(f"Carregando mapeamento de {fundo}…")
        
        # Exibe o caminho absoluto do arquivo para transparência total
        path = self._vm.obter_caminho_fundo(fundo)
        if path:
            self._lbl_caminho.setText(f"Arquivo: {path}")
        else:
            self._lbl_caminho.setText("Arquivo: Não configurado no Registro")

        self._vm.carregar_mapeamento(fundo)

    def _on_carregar_arquivo(self) -> None:
        fundo = self._cb_fundo.currentText()
        if not fundo or fundo == "Nenhum fundo cadastrado":
            return

        self._progress.setVisible(True)
        self._btn_query.setEnabled(False)
        self._lbl_status.setText("Carregando e processando portfólio físico...")
        self._vm.carregar_arquivo_carteira(fundo)

    def _on_variaveis_prontas(self, variaveis: list[dict]) -> None:
        self._progress.setVisible(False)
        self._btn_query.setEnabled(True)
        self._variaveis = variaveis

        # Calcula o status inicial dos chips
        cards_cd = self._tab_cd._card_panel.cards()
        
        # Atualiza os rótulos genéricos e valores de hover nos cards que já foram carregados
        for card in cards_cd:
            card.atualizar_variaveis_carregadas(variaveis)
            
        cards_mec = self._tab_mec._card_panel.cards()
        for card in cards_mec:
            card.atualizar_variaveis_carregadas(variaveis)

        cats_cd = [(c.categoria, c.atributos_mapeados()) for c in cards_cd]
        status_map = self._vm.calcular_status(variaveis, cats_cd)

        self._tab_cd._chip_panel.carregar(variaveis, status_map)
        self._tab_mec._chip_panel.carregar(variaveis, status_map)

        total = len(variaveis)
        self._lbl_status.setText(f"✓ {total} variáveis de planilha e taxas carregadas com sucesso!")
        self._btn_save.setEnabled(True)

    def _on_mapeamento_carregado(
        self,
        cd_cats: list[tuple[str, list[dict]]],
        mec_cats: list[tuple[str, list[dict]]],
    ) -> None:
        self._tab_cd._card_panel.carregar(cd_cats, self._on_mapping_changed)
        self._tab_mec._card_panel.carregar(mec_cats, self._on_mapping_changed)
        self._lbl_status.setText(
            f"Mapeamento de {self._fundo_atual} carregado. Clique em '📂 Carregar Arquivo' para ler variáveis."
        )
        self._btn_save.setEnabled(True)

    def _on_mapping_changed(self) -> None:
        if not self._variaveis:
            return

        # CD Tab
        cards_cd = self._tab_cd._card_panel.cards()
        cats_cd = [(c.categoria, c.atributos_mapeados()) for c in cards_cd]
        status_cd = self._vm.calcular_status(self._variaveis, cats_cd)
        for label, status in status_cd.items():
            self._tab_cd._chip_panel.atualizar_status(label, status)

        # MEC Tab
        cards_mec = self._tab_mec._card_panel.cards()
        cats_mec = [(c.categoria, c.atributos_mapeados()) for c in cards_mec]
        status_mec = self._vm.calcular_status(self._variaveis, cats_mec)
        for label, status in status_mec.items():
            self._tab_mec._chip_panel.atualizar_status(label, status)

        novos = sum(1 for s in status_cd.values() if s == "livre")
        self._lbl_status.setText(f"✓ Mapeamento alterado. {novos} variáveis livres.")

    def _on_salvar(self) -> None:
        if not self._fundo_atual:
            return

        resp = QMessageBox.question(
            self,
            "Salvar Mapeamento",
            f"Deseja salvar o mapeamento de {self._fundo_atual}?\n"
            "Um backup histórico será gerado automaticamente."
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        cards_cd  = self._tab_cd._card_panel.cards()
        cards_mec = self._tab_mec._card_panel.cards()
        self._vm.salvar(self._fundo_atual, cards_cd, cards_mec)

    def _on_salvo(self, fundo: str) -> None:
        self._lbl_status.setStyleSheet(f"color: {COLORS['success']}; font-size: 11px;")
        self._lbl_status.setText(f"✔ Mapeamento de {fundo} salvo com sucesso!")

    def _on_erro(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._btn_query.setEnabled(True)
        self._lbl_status.setStyleSheet(f"color: {COLORS['error']}; font-size: 11px;")
        self._lbl_status.setText(f"Erro: {msg}")
        QMessageBox.critical(self, "Erro", msg)
