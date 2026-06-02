"""
MainWindow — janela principal da aplicação.
Layout: Sidebar recolhível à esquerda + QStackedWidget à direita.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon, QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from src.gui.styles import COLORS
from src.gui.pages.launcher_page import LauncherPage
from src.gui.pages.mapping_editor_page import MappingEditorPage
from src.gui.pages.api_launcher_page import ApiLauncherPage
from src.gui.pages.api_mapping_page import ApiMappingPage
from src.gui.pages.file_mapping_page import FileMappingPage
from src.gui.pages.fundos_page import FundosPage


# Definição das páginas da sidebar
_PAGINAS = [
    ("🚀", "Lançamentos",     LauncherPage),
    ("🌐", "Ingestão API",    ApiLauncherPage),
    ("🔗", "Mapeamento API",  ApiMappingPage),
    ("📂", "Mapeamento Arq",  FileMappingPage),
    ("🏦", "Fundos",          FundosPage),
   # ("🗂️", "Mapeamentos",    MappingEditorPage),
]


class _NavButton(QPushButton):
    """Botão de navegação da sidebar."""

    def __init__(self, icon: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(f"  {icon}  {label}", parent)
        self.setObjectName("nav_btn")
        self.setCheckable(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        # Força atualização do estilo Qt
        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QMainWindow):
    """
    Janela principal da aplicação Carmel Capital.

    Sidebar fixa à esquerda com botões de navegação.
    Área direita: QStackedWidget que troca de página sem recriar widgets.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Carmel Capital — Gestão de Carteiras")
        self.setMinimumSize(1100, 700)
        self.resize(1300, 800)

        self._paginas_instanciadas: dict[int, QWidget] = {}
        self._btn_nav: list[_NavButton] = []
        self._pagina_atual = 0

        self._setup_ui()
        self._navegar(0)  # abre na página de Lançamentos

    def _setup_ui(self) -> None:
        # Widget central
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ----------------------------------------------------------------
        # Sidebar
        # ----------------------------------------------------------------
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 16)
        sidebar_layout.setSpacing(0)

        # Logo
        logo_frame = QWidget()
        logo_layout = QVBoxLayout(logo_frame)
        logo_layout.setContentsMargins(16, 24, 16, 16)

        lbl_logo = QLabel("Carmel Capital")
        lbl_logo.setObjectName("sidebar_title")
        lbl_logo.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))

        lbl_sub = QLabel("Sistema de Carteiras")
        lbl_sub.setObjectName("sidebar_subtitle")

        logo_layout.addWidget(lbl_logo)
        logo_layout.addWidget(lbl_sub)
        sidebar_layout.addWidget(logo_frame)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        sidebar_layout.addWidget(sep)
        sidebar_layout.addSpacing(12)

        # Botões de navegação
        for i, (icon, label, _PageClass) in enumerate(_PAGINAS):
            btn = _NavButton(icon, label)
            btn.clicked.connect(lambda checked=False, idx=i: self._navegar(idx))
            sidebar_layout.addWidget(btn)
            self._btn_nav.append(btn)

        sidebar_layout.addStretch()

        # Versão na base da sidebar
        lbl_versao = QLabel("v2.0 — Fase 2")
        lbl_versao.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_versao.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px; padding: 8px;")
        sidebar_layout.addWidget(lbl_versao)

        main_layout.addWidget(sidebar)

        # ----------------------------------------------------------------
        # Área de conteúdo
        # ----------------------------------------------------------------
        content_area = QFrame()
        content_area.setObjectName("content_area")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._stack = QStackedWidget()
        content_layout.addWidget(self._stack)

        # Pré-instancia todas as páginas (evita delay ao navegar)
        for i, (_, _, PageClass) in enumerate(_PAGINAS):
            page = PageClass()
            self._stack.addWidget(page)
            self._paginas_instanciadas[i] = page

        main_layout.addWidget(content_area)

        # ----------------------------------------------------------------
        # Status bar
        # ----------------------------------------------------------------
        status = QStatusBar()
        self.setStatusBar(status)
        status.showMessage("Pronto  |  Sistema de Carteiras Carmel Capital")

    # ------------------------------------------------------------------
    # Navegação
    # ------------------------------------------------------------------

    def _navegar(self, indice: int) -> None:
        self._pagina_atual = indice
        self._stack.setCurrentIndex(indice)

        for i, btn in enumerate(self._btn_nav):
            btn.set_active(i == indice)

        nomes = [label for _, label, _ in _PAGINAS]
        self.statusBar().showMessage(
            f"Página: {nomes[indice]}  |  Sistema de Carteiras Carmel Capital"
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        """Confirmação antes de fechar."""
        # Futuramente: verificar se há alterações não salvas no editor
        event.accept()
