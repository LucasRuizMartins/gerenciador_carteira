"""
LauncherPage — tela de execução de fundos (substitui o Tkinter).
Mostra um grid de cards para cada fundo do REGISTRO.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.viewmodels.launcher_vm import LauncherViewModel
from src.gui.widgets.log_panel import LogPanel
from src.gui.styles import COLORS


class _FundCard(QPushButton):
    """Card clicável de um fundo."""

    def __init__(self, nome: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.nome = nome
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(72)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)

        label = QLabel(nome)
        label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        label.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")

        self._status = QLabel("Aguardando")
        self._status.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent;")

        layout.addWidget(label)
        layout.addWidget(self._status)

    def set_status(self, msg: str, color: str = COLORS["text_muted"]) -> None:
        self._status.setText(msg)
        self._status.setStyleSheet(f"color: {color}; font-size: 11px; background: transparent;")


class _AbaDialog(QDialog):
    """Diálogo de seleção da aba antes de executar."""

    def __init__(self, nome_fundo: str, vm: LauncherViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Executar — {nome_fundo}")
        self.setFixedSize(320, 160)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        layout.addWidget(QLabel(f"Selecione a aba para <b>{nome_fundo}</b>:"))

        self.combo = QComboBox()
        self.combo.addItems(vm.obter_abas_excel(nome_fundo))
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def aba_selecionada(self) -> str:
        return self.combo.currentText()


class CollapsibleSection(QWidget):
    """Seção colapsável/expansível para agrupar fundos por administradora."""

    def __init__(self, titulo: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.titulo = titulo
        self._aberto = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Cabeçalho da seção
        self.btn_header = QPushButton()
        self.btn_header.setFixedHeight(46)
        self.btn_header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_header.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                text-align: left;
                padding-left: 18px;
                color: {COLORS['text']};
                font-weight: bold;
                font-size: 13px;
                font-family: "Segoe UI";
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_alt']};
                border-color: {COLORS['accent_hover']};
            }}
        """)
        self.btn_header.clicked.connect(self.toggle)
        layout.addWidget(self.btn_header)

        # Área de conteúdo (onde fica a grid de fundos)
        self.content_area = QWidget()
        self.content_area.setVisible(False)
        self.content_layout = QGridLayout(self.content_area)
        self.content_layout.setContentsMargins(8, 12, 8, 12)
        self.content_layout.setSpacing(12)
        layout.addWidget(self.content_area)

        self._atualizar_header()

    def toggle(self) -> None:
        self._aberto = not self._aberto
        self.content_area.setVisible(self._aberto)
        self._atualizar_header()

    def _atualizar_header(self) -> None:
        chevron = "▼" if self._aberto else "▶"
        self.btn_header.setText(f"{chevron}   {self.titulo}")

    def add_card(self, card: QWidget, row: int, col: int) -> None:
        self.content_layout.addWidget(card, row, col)


class LauncherPage(QWidget):
    """
    Página principal de execução de fundos.
    Substitui completamente o executar_carteira.py (Tkinter).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = LauncherViewModel(self)
        self._cards: dict[str, _FundCard] = {}
        self._em_andamento: int = 0
        self._setup_ui()
        self._conectar_vm()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(20)

        # Cabeçalho
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel("Lançamentos")
        title.setObjectName("page_title")
        subtitle = QLabel("Selecione um fundo para gerar o relatório diário.")
        subtitle.setObjectName("page_subtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        header.addStretch()

        # Barra de ações
        self._btn_refresh = QPushButton("🔄 Atualizar")
        self._btn_refresh.setToolTip("Recarrega a lista de fundos cadastrados")
        self._btn_refresh.setObjectName("btn_secondary")
        self._btn_refresh.clicked.connect(self._popular_grid)
        header.addWidget(self._btn_refresh)

        self._btn_batch = QPushButton("⚡ Processar Todos")
        self._btn_batch.setToolTip("Processa todos os fundos com CD_ATUAL")
        self._btn_batch.clicked.connect(self._on_batch)
        header.addWidget(self._btn_batch)

        root.addLayout(header)

        # Barra de progresso (oculta por padrão)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # modo indeterminado
        self._progress.setFixedHeight(6)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # Grid de cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self._grid_layout = QVBoxLayout(container)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setSpacing(16)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(container)

        self._popular_grid()
        root.addWidget(scroll, stretch=2)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        # Painel de log
        log_label = QLabel("Log de Execução")
        log_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 600;")
        root.addWidget(log_label)

        self._log = LogPanel(self)
        self._log.setFixedHeight(180)
        self._log.instalar()  # conecta ao logger raiz
        root.addWidget(self._log)

        # Botão limpar log
        btn_limpar = QPushButton("Limpar Log")
        btn_limpar.setObjectName("btn_ghost")
        btn_limpar.setFixedWidth(100)
        btn_limpar.clicked.connect(self._log.limpar)
        root.addWidget(btn_limpar, alignment=Qt.AlignmentFlag.AlignRight)

    def _popular_grid(self) -> None:
        self._cards.clear()
        
        # Remove widgets anteriores da grid principal
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        agrupados = self._vm.fundos_agrupados()
        
        # Cria as seções colapsáveis na grid principal
        for adm, fundos in sorted(agrupados.items()):
            if not fundos:
                continue
                
            section = CollapsibleSection(adm, parent=self)
            self._grid_layout.addWidget(section)
            
            # Popula a seção com os cards em grid
            cols = 3
            for i, nome in enumerate(fundos):
                card = _FundCard(nome)
                card.clicked.connect(lambda checked=False, n=nome: self._on_card_click(n))
                self._cards[nome] = card
                section.add_card(card, i // cols, i % cols)

    def _conectar_vm(self) -> None:
        self._vm.iniciando.connect(self._on_iniciando)
        self._vm.sucesso.connect(self._on_sucesso)
        self._vm.erro.connect(self._on_erro)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._popular_grid()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_card_click(self, nome: str) -> None:
        dlg = _AbaDialog(nome, self._vm, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._vm.executar(nome, dlg.aba_selecionada)

    def _on_batch(self) -> None:
        fundos = self._vm.fundos_disponiveis()
        resp = QMessageBox.question(
            self,
            "Processar Todos",
            f"Isso irá processar {len(fundos)} fundos com aba CD_ATUAL.\nConfirmar?",
        )
        if resp == QMessageBox.StandardButton.Yes:
            self._vm.executar_batch({f: "CD_ATUAL" for f in fundos})

    def _on_iniciando(self, nome: str) -> None:
        self._em_andamento += 1
        self._progress.setVisible(True)
        card = self._cards.get(nome)
        if card:
            card.set_status("⏳ Processando...", COLORS["warning"])

    def _on_sucesso(self, nome: str, segundos: float) -> None:
        self._em_andamento = max(0, self._em_andamento - 1)
        if self._em_andamento == 0:
            self._progress.setVisible(False)
        card = self._cards.get(nome)
        if card:
            card.set_status(f"✔ Concluído em {segundos:.1f}s", COLORS["success"])

    def _on_erro(self, nome: str, msg: str) -> None:
        self._em_andamento = max(0, self._em_andamento - 1)
        if self._em_andamento == 0:
            self._progress.setVisible(False)
        card = self._cards.get(nome)
        if card:
            card.set_status("✖ Erro", COLORS["error"])
        QMessageBox.critical(self, f"Erro — {nome}", msg)
