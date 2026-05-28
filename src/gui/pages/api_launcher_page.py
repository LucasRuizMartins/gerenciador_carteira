from __future__ import annotations

# pyrefly: ignore [missing-import]
from PySide6.QtCore import Qt, QDate
# pyrefly: ignore [missing-import]
from PySide6.QtGui import QFont, QShowEvent
# pyrefly: ignore [missing-import]
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.viewmodels.launcher_vm import LauncherViewModel
from src.gui.widgets.log_panel import LogPanel
from src.gui.styles import COLORS
from src.registry import obter_fundos_api

class ApiLauncherPage(QWidget):
    """
    Página dedicada para execução de fundos cujo input venha via API.
    """
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = LauncherViewModel(self)
        self._em_andamento: bool = False
        self._setup_ui()
        self._conectar_vm()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(20)

        # Cabeçalho
        title = QLabel("Ingestão via API")
        title.setObjectName("page_title")
        subtitle = QLabel("Busque os dados direto na nuvem para gerar o relatório gerencial.")
        subtitle.setObjectName("page_subtitle")
        root.addWidget(title)
        root.addWidget(subtitle)
        
        # Container do Formulário
        form_frame = QFrame()
        form_frame.setStyleSheet(f"background-color: {COLORS['surface']}; border-radius: 8px;")
        form_layout = QFormLayout(form_frame)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(16)
        
        # 1. Selecionar Fundo
        self._cb_fundo = QComboBox()
        self._cb_fundo.setFixedHeight(36)

            
        form_layout.addRow(self._estilizar_label("Selecione o Fundo:"), self._cb_fundo)
        
        # 2. Selecionar Data
        self._date_picker = QDateEdit()
        self._date_picker.setCalendarPopup(True)
        self._date_picker.setFixedHeight(36)
        # Default: dia atual - 1
        ontem = QDate.currentDate().addDays(-1)
        self._date_picker.setDate(ontem)
        form_layout.addRow(self._estilizar_label("Data de Referência:"), self._date_picker)
        
        root.addWidget(form_frame)
        
        # Botão de Execução
        btn_layout = QHBoxLayout()
        self._btn_executar = QPushButton("⚡ Buscar e Processar Relatório")
        self._btn_executar.setFixedHeight(45)
        self._btn_executar.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._btn_executar.setEnabled(False) # Habilitado por _popular_fundos
        self._btn_executar.clicked.connect(self._on_executar)
        btn_layout.addStretch()
        btn_layout.addWidget(self._btn_executar)
        root.addLayout(btn_layout)

        # Barra de progresso
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(6)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        root.addSpacing(16)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        # Painel de log
        log_label = QLabel("Log de Execução")
        log_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 600;")
        root.addWidget(log_label)

        self._log = LogPanel(self)
        self._log.setFixedHeight(220)
        self._log.instalar()
        root.addWidget(self._log)
        
        # Botão limpar log
        btn_limpar = QPushButton("Limpar Log")
        btn_limpar.setObjectName("btn_ghost")
        btn_limpar.setFixedWidth(100)
        btn_limpar.clicked.connect(self._log.limpar)
        root.addWidget(btn_limpar, alignment=Qt.AlignmentFlag.AlignRight)
        
        root.addStretch()

    def _estilizar_label(self, texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {COLORS['text']};")
        return lbl

    def _conectar_vm(self) -> None:
        self._vm.iniciando.connect(self._on_iniciando)
        self._vm.sucesso.connect(self._on_sucesso)
        self._vm.erro.connect(self._on_erro)
        self._vm.avisos.connect(self._on_avisos)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._popular_fundos()

    def _popular_fundos(self) -> None:
        atual = self._cb_fundo.currentText()
        self._cb_fundo.blockSignals(True)
        self._cb_fundo.clear()
        
        fundos_api = obter_fundos_api()
        if fundos_api:
            self._cb_fundo.addItems(fundos_api)
            self._cb_fundo.setEnabled(True)
            self._btn_executar.setEnabled(True)
            
            idx = self._cb_fundo.findText(atual)
            if idx >= 0:
                self._cb_fundo.setCurrentIndex(idx)
        else:
            self._cb_fundo.addItem("Nenhum fundo API cadastrado")
            self._cb_fundo.setEnabled(False)
            self._btn_executar.setEnabled(False)
            
        self._cb_fundo.blockSignals(False)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_executar(self) -> None:
        fundo = self._cb_fundo.currentText()
        if not fundo or fundo == "Nenhum fundo API cadastrado":
            return
            
        data_selecionada = self._date_picker.date().toPython()
        
        resp = QMessageBox.question(
            self,
            "Confirmar Processamento",
            f"Fundo: {fundo}\nData: {data_selecionada.strftime('%d/%m/%Y')}\n\nDeseja buscar e processar?",
        )
        if resp == QMessageBox.StandardButton.Yes:
            self._vm.executar(nome_fundo=fundo, aba="CD_ATUAL", data_referencia=data_selecionada)

    def _on_iniciando(self, nome: str) -> None:
        self._em_andamento = True
        self._progress.setVisible(True)
        self._btn_executar.setEnabled(False)
        self._btn_executar.setText("⏳ Processando...")

    def _on_sucesso(self, nome: str, segundos: float) -> None:
        self._em_andamento = False
        self._progress.setVisible(False)
        self._btn_executar.setEnabled(True)
        self._btn_executar.setText("⚡ Buscar e Processar Relatório")
        
        QMessageBox.information(
            self,
            "Sucesso",
            f"Relatório do {nome} gerado com sucesso em {segundos:.1f}s!"
        )

    def _on_erro(self, nome: str, msg: str) -> None:
        self._em_andamento = False
        self._progress.setVisible(False)
        self._btn_executar.setEnabled(True)
        self._btn_executar.setText("⚡ Buscar e Processar Relatório")
        
        QMessageBox.critical(self, f"Erro — {nome}", msg)

    def _on_avisos(self, nome: str, lista_avisos: list[str]) -> None:
        formatted_warnings = "\n".join(f"• {w}" for w in lista_avisos)
        QMessageBox.warning(
            self,
            f"Avisos de Ingestão — {nome}",
            f"Atenção! O relatório foi gerado, mas alguns campos não puderam ser recuperados ou retornaram 0.0 da API:\n\n{formatted_warnings}\n\nPor favor, valide se esses valores estão corretos na planilha gerada."
        )
