"""
ApiMappingPage — interface drag-and-drop para mapeamento de atributos JSON da API
para colunas do relatório Excel.

Layout:
    [Seletor de fundo / data + botão atualizar]
    ─────────────────────────────────────────────
    [Painel Atributos API]  |  [Painel Colunas Excel]
    ─────────────────────────────────────────────
    [status bar + botão salvar]
"""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, QDate, QSize
from PySide6.QtGui import QFont, QColor, QShowEvent
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFrame, QHBoxLayout, QInputDialog,
    QLabel, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSplitter, QTabWidget, QVBoxLayout, QWidget,
    QTreeWidget, QTreeWidgetItem,
)

from src.gui.styles import COLORS
from src.gui.viewmodels.api_mapping_vm import ApiMappingViewModel
from src.gui.widgets.api_attr_chip import ApiAttrChip
from src.gui.widgets.excel_column_card import ExcelColumnCard


class _ChipPanel(QWidget):
    """Painel esquerdo: exibe os chips de atributos da API agrupados hierarquicamente."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        lbl = QLabel("Atributos detectados na API")
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

        self._chips: dict[str, ApiAttrChip] = {}  # label → chip

    def carregar(self, atributos: list[dict], status_map: dict[str, str]) -> None:
        """Recria a árvore de atributos organizando-os por caminhos hierárquicos."""
        self._tree.clear()
        self._chips.clear()

        # Cache de nós intermediários para evitar duplicar pastas
        nos_cache: dict[tuple[str, ...], QTreeWidgetItem] = {}

        for attr in atributos:
            caminho_json = attr.get("caminho_json", "")
            chave_filtro = attr.get("chave_filtro_json")
            valor_filtro = attr.get("valor_filtro_json")
            campo_valor = attr.get("campo_valor_json")
            label = attr.get("label", caminho_json)
            status = status_map.get(label, "livre")

            # Cria hierarquia a partir do caminho do JSON
            partes_pais: list[str] = []
            if caminho_json:
                partes_pais.extend(caminho_json.split("."))

            if chave_filtro and valor_filtro:
                # Se tem filtro, coloca o filtro como um nó intermediário
                partes_pais.append(f"{chave_filtro} = {valor_filtro}")
                nome_folha = campo_valor or "valor"
            else:
                # Caso contrário, o último elemento do caminho é o nome da folha
                if partes_pais:
                    nome_folha = partes_pais.pop()
                else:
                    nome_folha = label

            # Monta a estrutura de pais da árvore
            parent_item = self._tree.invisibleRootItem()
            caminho_acumulado: list[str] = []

            for parte in partes_pais:
                caminho_acumulado.append(parte)
                chave_cache = tuple(caminho_acumulado)

                if chave_cache not in nos_cache:
                    item = QTreeWidgetItem(parent_item)
                    item.setText(0, f"📁 {parte}")
                    item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
                    item.setForeground(0, QColor(COLORS["accent_hover"]))
                    nos_cache[chave_cache] = item

                parent_item = nos_cache[chave_cache]

            # Adiciona a folha contendo o chip arrastável
            folha_item = QTreeWidgetItem(parent_item)

            chip_payload = dict(attr)
            chip_payload["label_curto"] = nome_folha  # exibe apenas o nome final no chip

            chip = ApiAttrChip(chip_payload, status=status)
            chip.setMinimumWidth(180)  # Garante boa largura para ler tudo!
            
            # Define o tamanho ideal do item na árvore para evitar achatamento vertical
            folha_item.setSizeHint(0, QSize(180, 36))
            
            self._tree.setItemWidget(folha_item, 0, chip)
            self._chips[label] = chip

        # Os nós (pastas) iniciarão fechados por padrão, conforme solicitado
        # (nenhuma chamada a setExpanded(True) é necessária, pois fechado é o padrão)

    def atualizar_status(self, label: str, status: str) -> None:
        if label in self._chips:
            self._chips[label].set_status(status)


class _CardPanel(QWidget):
    """Painel direito: exibe os cards drop-target das colunas do Excel."""

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
        """Recria os cards a partir das categorias."""
        self._changed_callback = changed_callback
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


class ApiMappingPage(QWidget):
    """
    Página principal de mapeamento visual de API → Excel.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = ApiMappingViewModel(self)
        self._fundo_atual: str | None = None
        self._atributos_api: list[dict] = []

        self._setup_ui()
        self._conectar_vm()
        self._popular_fundos()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)

        # Cabeçalho
        title = QLabel("Mapeamento Visual de API")
        title.setObjectName("page_title")
        subtitle = QLabel(
            "Arraste os atributos detectados na API sobre as colunas do relatório Excel. "
            "Múltiplos atributos na mesma coluna são somados automaticamente."
        )
        subtitle.setObjectName("page_subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        # Barra de controles
        ctrl = QFrame()
        ctrl.setStyleSheet(
            f"background-color: {COLORS['surface']}; border-radius: 8px;"
        )
        ctrl_layout = QHBoxLayout(ctrl)
        ctrl_layout.setContentsMargins(16, 12, 16, 12)
        ctrl_layout.setSpacing(12)

        # Seletor de fundo
        self._cb_fundo = QComboBox()
        self._cb_fundo.setFixedHeight(36)
        self._cb_fundo.setMinimumWidth(160)
        self._cb_fundo.currentTextChanged.connect(self._on_fundo_changed)
        ctrl_layout.addWidget(QLabel("Fundo:"))
        ctrl_layout.addWidget(self._cb_fundo)

        # Data
        self._date_picker = QDateEdit()
        self._date_picker.setCalendarPopup(True)
        self._date_picker.setFixedHeight(36)
        self._date_picker.setDate(QDate.currentDate().addDays(-1))
        ctrl_layout.addWidget(QLabel("Data:"))
        ctrl_layout.addWidget(self._date_picker)

        ctrl_layout.addStretch()

        # Botão consultar API
        self._btn_query = QPushButton("🔄 Consultar API")
        self._btn_query.setFixedHeight(36)
        self._btn_query.setEnabled(False)
        self._btn_query.clicked.connect(self._on_consultar)
        ctrl_layout.addWidget(self._btn_query)

        root.addWidget(ctrl)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # Splitter principal: chips | cards
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Tabs CD / MEC — cada aba tem seu próprio painel de cards
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
        """Cria um splitter com ChipPanel à esquerda e CardPanel à direita."""
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

        # Guarda referências
        w._chip_panel = chips
        w._card_panel = cards
        return w

    # ------------------------------------------------------------------
    # VM + slots
    # ------------------------------------------------------------------

    def _conectar_vm(self) -> None:
        self._vm.atributos_prontos.connect(self._on_atributos_prontos)
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

        fundos = self._vm.fundos_api()
        if fundos:
            self._cb_fundo.addItems(fundos)
            self._cb_fundo.setEnabled(True)
            self._btn_query.setEnabled(True)
            
            idx = self._cb_fundo.findText(atual)
            if idx >= 0:
                self._cb_fundo.setCurrentIndex(idx)
        else:
            self._cb_fundo.addItem("Nenhum fundo API cadastrado")
            self._cb_fundo.setEnabled(False)
            self._btn_query.setEnabled(False)
            
        self._cb_fundo.blockSignals(False)
        
        # Emite manualmente se a seleção mudou devido à atualização
        if self._cb_fundo.currentText() != atual:
            self._on_fundo_changed(self._cb_fundo.currentText())

    def _on_fundo_changed(self, fundo: str) -> None:
        if not fundo or fundo == "Nenhum fundo API cadastrado":
            return
        self._fundo_atual = fundo
        self._btn_save.setEnabled(False)
        self._lbl_status.setText(f"Carregando mapeamento de {fundo}…")
        self._vm.carregar_mapeamento(fundo)

    def _on_consultar(self) -> None:
        fundo = self._cb_fundo.currentText()
        if not fundo or fundo == "Nenhum fundo API cadastrado":
            return

        self._progress.setVisible(True)
        self._btn_query.setEnabled(False)
        self._lbl_status.setText("Consultando API…")
        data_ref = self._date_picker.date().toPython()
        self._vm.consultar_api(fundo, data_ref)

    def _on_atributos_prontos(self, atributos: list[dict]) -> None:
        self._progress.setVisible(False)
        self._btn_query.setEnabled(True)
        self._atributos_api = atributos

        # Calcula status dos chips vs mapeamento atual (CD)
        cards_cd = self._tab_cd._card_panel.cards()
        cats_cd = [(c.categoria, c.atributos_mapeados()) for c in cards_cd]
        status_map = self._vm.calcular_status(atributos, cats_cd)

        self._tab_cd._chip_panel.carregar(atributos, status_map)
        self._tab_mec._chip_panel.carregar(atributos, status_map)

        total = len(atributos)
        novos = sum(1 for s in status_map.values() if s == "livre")
        self._lbl_status.setText(
            f"✓ {total} atributos detectados — {novos} sem mapeamento"
        )
        self._btn_save.setEnabled(True)

    def _on_mapeamento_carregado(
        self,
        cd_cats: list[tuple[str, list[dict]]],
        mec_cats: list[tuple[str, list[dict]]],
    ) -> None:
        self._tab_cd._card_panel.carregar(cd_cats, self._on_mapping_changed)
        self._tab_mec._card_panel.carregar(mec_cats, self._on_mapping_changed)
        self._lbl_status.setText(
            f"Mapeamento de {self._fundo_atual} carregado. "
            "Clique em '🔄 Consultar API' para detectar atributos."
        )
        self._btn_save.setEnabled(True)

    def _on_mapping_changed(self) -> None:
        """Chamado sempre que um chip for arrastado/solto ou removido de um card."""
        if not self._atributos_api:
            return

        # CD Tab
        cards_cd = self._tab_cd._card_panel.cards()
        cats_cd = [(c.categoria, c.atributos_mapeados()) for c in cards_cd]
        status_cd = self._vm.calcular_status(self._atributos_api, cats_cd)
        for label, status in status_cd.items():
            self._tab_cd._chip_panel.atualizar_status(label, status)

        # MEC Tab
        cards_mec = self._tab_mec._card_panel.cards()
        cats_mec = [(c.categoria, c.atributos_mapeados()) for c in cards_mec]
        status_mec = self._vm.calcular_status(self._atributos_api, cats_mec)
        for label, status in status_mec.items():
            self._tab_mec._chip_panel.atualizar_status(label, status)

        novos = sum(1 for s in status_cd.values() if s == "livre")
        self._lbl_status.setText(
            f"✓ Mapeamento alterado. {novos} atributos livres (sem mapeamento CD)."
        )

    def _on_salvar(self) -> None:
        if not self._fundo_atual:
            return

        resp = QMessageBox.question(
            self,
            "Salvar Mapeamento",
            f"Salvar o mapeamento de {self._fundo_atual}?\n"
            "Um backup da versão atual será criado automaticamente."
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


# ---------------------------------------------------------------------------
# FlowLayout simples (PySide6 não inclui por padrão)
# ---------------------------------------------------------------------------

from PySide6.QtCore import QRect, QSize, QPoint
from PySide6.QtWidgets import QLayout, QLayoutItem, QSizePolicy


class _FlowLayout(QLayout):
    """Layout que quebra widgets em múltiplas linhas como texto."""

    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = 4) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self.setContentsMargins(margin, margin, margin, margin)
        self._spacing = spacing
        if parent:
            self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        eff = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y = eff.x(), eff.y()
        row_h = 0

        for item in self._items:
            wid = item.widget()
            sh = item.sizeHint()
            next_x = x + sh.width() + self._spacing
            if next_x > eff.right() and row_h > 0:
                x = eff.x()
                y += row_h + self._spacing
                next_x = x + sh.width() + self._spacing
                row_h = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), sh))
            x = next_x
            row_h = max(row_h, sh.height())

        return y + row_h - rect.y() + m.bottom()
