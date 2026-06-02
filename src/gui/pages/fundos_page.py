"""
FundosPage — Página de cadastro e gerenciamento de fundos externos (Multi-API).

Permite ao usuário:
  - Ver todos os fundos cadastrados por ele via interface gráfica.
  - Adicionar novos fundos de qualquer administradora suportada (Apex, etc.).
  - Editar ou remover fundos existentes.
  - Testar a conexão com a API antes de salvar.

Os fundos cadastrados aqui são persistidos em fundos_api.json e ficam
disponíveis nas telas de Ingestão API e Mapeamento API imediatamente.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QComboBox,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QProgressBar,
)

from src.gui.styles import COLORS
from src.gui.viewmodels.fundos_vm import FundosViewModel


# ---------------------------------------------------------------------------
# Dialog de cadastro / edição
# ---------------------------------------------------------------------------

class _FundoDialog(QDialog):
    """Dialog modal para criar ou editar um fundo externo."""

    def __init__(
        self,
        administradoras: list[str],
        entry: dict | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._adms = administradoras
        self._editando = entry is not None
        self.setWindowTitle("Editar Fundo" if self._editando else "Novo Fundo")
        self.setMinimumWidth(550)
        self.setModal(True)
        
        # Se estiver editando, busca o caminho_carteira atual no config.json
        if entry:
            from src.config.settings import configuracoes
            try:
                cfg = configuracoes()
                chave_gerencial = entry.get("chave_gerencial", "")
                caminho = cfg.get("carteiras", {}).get(chave_gerencial, "")
                entry["caminho_carteira"] = caminho
            except Exception:
                entry["caminho_carteira"] = ""
                
        self._setup_ui(entry or {})

    def _setup_ui(self, entry: dict) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(20)

        # Título
        titulo = QLabel("✏️ Editar Fundo" if self._editando else "➕ Novo Fundo")
        titulo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        titulo.setStyleSheet(f"color: {COLORS['text']};")
        layout.addWidget(titulo)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(sep)

        # Formulário
        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def _label(texto: str) -> QLabel:
            lbl = QLabel(texto)
            lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color: {COLORS['text']};")
            return lbl

        def _field(placeholder: str, valor: str = "") -> QLineEdit:
            ed = QLineEdit()
            ed.setPlaceholderText(placeholder)
            ed.setText(valor)
            ed.setFixedHeight(36)
            return ed

        # Chave (slug)
        self._ed_chave = _field("Ex: NOVO_FIDC_API", entry.get("chave", ""))
        self._ed_chave.setEnabled(not self._editando)  # não muda chave ao editar
        if self._editando:
            self._ed_chave.setToolTip("A chave não pode ser alterada após o cadastro.")
        form.addRow(_label("Chave (slug):"), self._ed_chave)

        # Nome de exibição
        self._ed_nome = _field("Ex: Novo FIDC Capital", entry.get("nome", ""))
        form.addRow(_label("Nome de Exibição:"), self._ed_nome)

        # Administradora (dropdown)
        self._cb_adm = QComboBox()
        self._cb_adm.setFixedHeight(36)
        for adm in self._adms:
            self._cb_adm.addItem(adm, userData=adm)
        # Seleciona a administradora atual se estiver editando
        adm_atual = entry.get("administrador", "APEX")
        idx_selecionado = 0
        for i in range(self._cb_adm.count()):
            if self._cb_adm.itemText(i).upper() == adm_atual.upper():
                idx_selecionado = i
                break
        self._cb_adm.setCurrentIndex(idx_selecionado)
        form.addRow(_label("Administradora:"), self._cb_adm)

        # doc_fundo_api (CNPJ / identificador)
        self._ed_doc = _field("CNPJ (apenas para APEX / API)", entry.get("doc_fundo_api", ""))
        form.addRow(_label("ID na API (CNPJ):"), self._ed_doc)

        # chave_gerencial
        self._ed_gerencial = _field("Chave do Excel de destino (ex: COBUCCIO FIDC)", entry.get("chave_gerencial", ""))
        form.addRow(_label("Chave Gerencial:"), self._ed_gerencial)

        # Caminho da Carteira Diária (com selecionador)
        self._ed_carteira = _field("Caminho relativo da carteira diária (.xlsx, .xlsb, .csv)", entry.get("caminho_carteira", ""))
        
        btn_selecionar = QPushButton("📁 ...")
        btn_selecionar.setFixedWidth(50)
        btn_selecionar.setFixedHeight(36)
        btn_selecionar.clicked.connect(self._on_selecionar_arquivo)
        
        carteira_layout = QHBoxLayout()
        carteira_layout.addWidget(self._ed_carteira)
        carteira_layout.addWidget(btn_selecionar)
        form.addRow(_label("Carteira Diária:"), carteira_layout)

        layout.addLayout(form)

        # Nota informativa
        nota = QLabel(
            "💡 Para fundos de arquivo local (Singulare, Genial, etc.), preencha o campo **Carteira Diária** "
            "clicando na pasta 📁. O sistema converterá automaticamente para um caminho dinâmico relativo "
            "para funcionar perfeitamente com outros usuários!"
        )
        nota.setWordWrap(True)
        nota.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        layout.addWidget(nota)

        # Botões
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("💾 Salvar")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        layout.addWidget(btns)

    def _on_selecionar_arquivo(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        from src.config.settings import configuracoes_validadas
        import os
        from pathlib import Path
        
        try:
            cfg = configuracoes_validadas()
            root_dir = cfg.paths.root_dir
            perfil_usuario = os.environ.get("USERPROFILE", os.path.expanduser("~"))
            diretorio_inicial = str(Path(perfil_usuario) / root_dir)
        except Exception:
            diretorio_inicial = ""
            
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Carteira Diária",
            diretorio_inicial,
            "Arquivos de Planilha (*.xlsx *.xlsb *.xlsm *.csv);;Todos os arquivos (*)"
        )
        
        if file_path:
            caminho_relativo = self._obter_caminho_relativo(file_path)
            self._ed_carteira.setText(caminho_relativo)

    def _obter_caminho_relativo(self, caminho_absoluto: str) -> str:
        from src.config.settings import configuracoes_validadas
        import os
        from pathlib import Path
        
        try:
            cfg = configuracoes_validadas()
            root_dir = cfg.paths.root_dir
            perfil_usuario = os.environ.get("USERPROFILE", os.path.expanduser("~"))
            base_dir = Path(perfil_usuario) / root_dir
            
            abs_path = Path(caminho_absoluto).resolve()
            base_dir_resolved = base_dir.resolve()
            
            try:
                rel_path = abs_path.relative_to(base_dir_resolved)
                return str(rel_path).replace("\\", "/")
            except ValueError:
                # Fallback: se tiver subpasta conhecida
                partes = abs_path.parts
                for i, part in enumerate(partes):
                    if "01 - OPERACIONAL" in part:
                        return "/".join(partes[i:]).replace("\\", "/")
                
                try:
                    rel_user = abs_path.relative_to(Path(perfil_usuario).resolve())
                    return str(rel_user).replace("\\", "/")
                except ValueError:
                    pass
                
                return abs_path.name
        except Exception:
            return os.path.basename(caminho_absoluto)

    def entry(self) -> dict:
        """Retorna o dict com os dados preenchidos no formulário."""
        adm = self._cb_adm.currentData()
        return {
            "chave":          self._ed_chave.text().upper().strip().replace(" ", "_"),
            "nome":           self._ed_nome.text().strip(),
            "administrador":  adm,
            "tipo_api":       adm.lower(),
            "doc_fundo_api":  self._ed_doc.text().strip(),
            "chave_gerencial": self._ed_gerencial.text().strip().upper(),
            "caminho_carteira": self._ed_carteira.text().strip(),
        }


# ---------------------------------------------------------------------------
# Página principal
# ---------------------------------------------------------------------------

class FundosPage(QWidget):
    """
    Página de gerenciamento de fundos externos (Multi-API / Arquivos Locais).

    Exibe uma tabela com todos os fundos cadastrados pelo usuário,
    com ações de adicionar, editar, excluir e testar conexão.
    """

    # Colunas da tabela
    _COLUNAS = ["Chave", "Nome", "Administrador", "API", "ID na API", "Chave Gerencial", "Ações"]
    _COL_CHAVE          = 0
    _COL_NOME           = 1
    _COL_ADMINISTRADOR  = 2
    _COL_API            = 3
    _COL_DOC            = 4
    _COL_GERENCIAL      = 5
    _COL_ACOES          = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = FundosViewModel(self)
        self._setup_ui()
        self._conectar_vm()
        self._atualizar_tabela(self._vm.listar())

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(20)

        # Cabeçalho
        title = QLabel("🏦 Gestão de Fundos")
        title.setObjectName("page_title")

        subtitle = QLabel(
            "Cadastre e gerencie fundos integrados via API (como Apex) ou fundos de arquivos locais "
            "(como Singulare, Genial, Terra, Avanti). Os fundos configurados ficam disponíveis no Launcher de Lançamentos."
        )
        subtitle.setObjectName("page_subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        # Barra de ações (topo)
        top_bar = QHBoxLayout()
        
        self._btn_cadastrar_adm = QPushButton("🏢 Cadastrar Administradora")
        self._btn_cadastrar_adm.setFixedHeight(40)
        self._btn_cadastrar_adm.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._btn_cadastrar_adm.setObjectName("btn_secondary")
        self._btn_cadastrar_adm.clicked.connect(self._on_cadastrar_administradora)
        
        self._btn_novo = QPushButton("➕  Novo Fundo")
        self._btn_novo.setFixedHeight(40)
        self._btn_novo.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._btn_novo.clicked.connect(self._on_novo)
        
        top_bar.addWidget(self._btn_cadastrar_adm)
        top_bar.addStretch()
        top_bar.addWidget(self._btn_novo)
        root.addLayout(top_bar)

        # Barra de teste de conexão (feedback)
        self._frame_teste = QFrame()
        self._frame_teste.setStyleSheet(
            f"background-color: {COLORS['surface']}; border-radius: 8px; padding: 4px;"
        )
        self._frame_teste.setVisible(False)
        teste_layout = QHBoxLayout(self._frame_teste)
        teste_layout.setContentsMargins(12, 8, 12, 8)
        self._lbl_teste = QLabel("Testando conexão...")
        self._lbl_teste.setStyleSheet(f"color: {COLORS['text_muted']};")
        self._progress_teste = QProgressBar()
        self._progress_teste.setRange(0, 0)
        self._progress_teste.setFixedHeight(4)
        self._progress_teste.setFixedWidth(100)
        teste_layout.addWidget(self._lbl_teste)
        teste_layout.addStretch()
        teste_layout.addWidget(self._progress_teste)
        root.addWidget(self._frame_teste)

        # Tabela
        self._tabela = QTableWidget()
        self._tabela.setColumnCount(len(self._COLUNAS))
        self._tabela.setHorizontalHeaderLabels(self._COLUNAS)
        self._tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._tabela.setAlternatingRowColors(True)
        self._tabela.setShowGrid(False)
        self._tabela.verticalHeader().setVisible(False)
        self._tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tabela.horizontalHeader().setSectionResizeMode(self._COL_ACOES, QHeaderView.ResizeMode.Fixed)
        self._tabela.setColumnWidth(self._COL_ACOES, 220)
        self._tabela.setStyleSheet(
            f"alternate-background-color: {COLORS['surface_alt']};"
        )
        root.addWidget(self._tabela)

        # Rodapé com nota
        nota = QLabel(
            "💡 Para fundos locais (Singulare, Genial, etc.), preencha o caminho da Carteira Diária. "
            "Para fundos de API (Apex), após cadastrar, vá em Mapeamento API para configurar a gravação."
        )
        nota.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        nota.setWordWrap(True)
        root.addWidget(nota)

    # ------------------------------------------------------------------
    # Conexão ViewModel
    # ------------------------------------------------------------------

    def _conectar_vm(self) -> None:
        self._vm.fundos_atualizados.connect(self._atualizar_tabela)
        self._vm.salvo.connect(self._on_salvo)
        self._vm.removido.connect(self._on_removido)
        self._vm.erro.connect(self._on_erro)
        self._vm.conexao_ok.connect(self._on_conexao_ok)
        self._vm.conexao_erro.connect(self._on_conexao_erro)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_novo(self) -> None:
        dialog = _FundoDialog(self._vm.listar_administradoras(), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._vm.salvar(dialog.entry())

    def _on_editar(self, chave: str) -> None:
        fundos = self._vm.listar()
        entry = next((f for f in fundos if f.get("chave") == chave), None)
        if not entry:
            return
        dialog = _FundoDialog(self._vm.listar_administradoras(), entry=entry, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._vm.salvar(dialog.entry())

    def _on_excluir(self, chave: str) -> None:
        resp = QMessageBox.question(
            self,
            "Confirmar Exclusão",
            f"Deseja remover o fundo '{chave}'?\n\nEssa ação não pode ser desfeita.",
        )
        if resp == QMessageBox.StandardButton.Yes:
            self._vm.remover(chave)

    def _on_testar(self, chave: str) -> None:
        fundos = self._vm.listar()
        entry = next((f for f in fundos if f.get("chave") == chave), None)
        if not entry:
            return
        self._frame_teste.setVisible(True)
        self._lbl_teste.setText(f"🔌 Testando conexão para {entry['nome']}...")
        self._vm.testar_conexao(
            chave,
            entry.get("tipo_api", "apex"),
            entry.get("doc_fundo_api", ""),
            entry.get("chave_gerencial", ""),
        )

    def _on_salvo(self, chave: str) -> None:
        QMessageBox.information(
            self, "Salvo", f"Fundo '{chave}' salvo e configurado com sucesso!"
        )

    def _on_removido(self, chave: str) -> None:
        QMessageBox.information(self, "Removido", f"Fundo '{chave}' removido com sucesso.")

    def _on_erro(self, msg: str) -> None:
        QMessageBox.critical(self, "Erro", msg)

    def _on_conexao_ok(self, chave: str, nome: str, data_pos: str, chave_gerencial: str) -> None:
        self._frame_teste.setVisible(False)
        QMessageBox.information(
            self,
            "Conexão bem-sucedida ✅",
            f"Fundo encontrado na API:\n\n"
            f"Nome: {nome}\n"
            f"Data de Posição: {data_pos}\n\n"
            f"A conexão está funcionando corretamente.",
        )
        
        resp = QMessageBox.question(
            self,
            "Mapeamento Automático",
            "Deseja fazer a leitura do Excel deste fundo para pré-cadastrar todas as colunas do CD e MEC?\n\nIsso preencherá o mapeamento automaticamente com as colunas reais do arquivo.",
        )
        if resp == QMessageBox.StandardButton.Yes:
            self._vm.gerar_mapeamento_padrao(chave, chave_gerencial)

    def _on_conexao_erro(self, msg: str) -> None:
        self._frame_teste.setVisible(False)
        QMessageBox.critical(
            self,
            "Falha na Conexão ❌",
            f"Não foi possível conectar à API:\n\n{msg}",
        )

    # ------------------------------------------------------------------
    # Atualização da tabela
    # ------------------------------------------------------------------

    def _on_cadastrar_administradora(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        nome, ok = QInputDialog.getText(
            self,
            "Cadastrar Administradora",
            "Nome da nova administradora (ex: Singulare, Genial, Terra, Avanti):",
        )
        if ok and nome.strip():
            nome_adm = nome.strip()
            try:
                self._vm.cadastrar_administradora(nome_adm)
                QMessageBox.information(
                    self,
                    "Sucesso",
                    f"Administradora '{nome_adm}' cadastrada com sucesso!"
                )
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "Erro ao Cadastrar",
                    f"Não foi possível cadastrar a administradora:\n\n{exc}"
                )

    def _atualizar_tabela(self, fundos: list[dict]) -> None:
        from src.registry import ROTULOS_APIS

        self._tabela.setRowCount(len(fundos))

        for row, fundo in enumerate(fundos):
            chave      = fundo.get("chave", "")
            nome       = fundo.get("nome", "")
            adm        = fundo.get("administrador", "APEX")
            tipo_api   = fundo.get("tipo_api", "apex")
            doc        = fundo.get("doc_fundo_api", "")
            gerencial  = fundo.get("chave_gerencial", "")
            
            # API label format: show "Apex (Prisma)" for apex, otherwise "Sem API (Ingestão Local)" or similar
            if adm.upper() == "APEX":
                rotulo_api = ROTULOS_APIS.get(tipo_api.lower(), "Apex (Prisma)")
            else:
                rotulo_api = "Sem API"

            self._tabela.setItem(row, self._COL_CHAVE,         QTableWidgetItem(chave))
            self._tabela.setItem(row, self._COL_NOME,          QTableWidgetItem(nome))
            self._tabela.setItem(row, self._COL_ADMINISTRADOR, QTableWidgetItem(adm))
            self._tabela.setItem(row, self._COL_API,           QTableWidgetItem(rotulo_api))
            self._tabela.setItem(row, self._COL_DOC,           QTableWidgetItem(doc))
            self._tabela.setItem(row, self._COL_GERENCIAL,     QTableWidgetItem(gerencial))

            # Centraliza certas colunas
            for col in (self._COL_CHAVE, self._COL_ADMINISTRADOR, self._COL_API, self._COL_GERENCIAL):
                item = self._tabela.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Célula de ações com botões
            acoes_widget = QWidget()
            acoes_layout = QHBoxLayout(acoes_widget)
            acoes_layout.setContentsMargins(4, 2, 4, 2)
            acoes_layout.setSpacing(6)

            btn_testar = QPushButton("🔌 Testar")
            btn_testar.setObjectName("btn_ghost")
            btn_testar.setFixedHeight(28)
            btn_testar.setFont(QFont("Segoe UI", 9))
            btn_testar.clicked.connect(lambda _, c=chave: self._on_testar(c))

            btn_editar = QPushButton("✏️")
            btn_editar.setObjectName("btn_secondary")
            btn_editar.setFixedSize(30, 28)
            btn_editar.setToolTip("Editar")
            btn_editar.clicked.connect(lambda _, c=chave: self._on_editar(c))

            btn_excluir = QPushButton("🗑️")
            btn_excluir.setObjectName("btn_danger")
            btn_excluir.setFixedSize(30, 28)
            btn_excluir.setToolTip("Excluir")
            btn_excluir.clicked.connect(lambda _, c=chave: self._on_excluir(c))

            acoes_layout.addWidget(btn_testar)
            acoes_layout.addWidget(btn_editar)
            acoes_layout.addWidget(btn_excluir)
            acoes_layout.addStretch()

            self._tabela.setCellWidget(row, self._COL_ACOES, acoes_widget)
            self._tabela.setRowHeight(row, 48)

        # Estado vazio
        if not fundos:
            self._tabela.setRowCount(1)
            item = QTableWidgetItem("Nenhum fundo cadastrado. Clique em '➕ Novo Fundo' para começar.")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(Qt.GlobalColor.gray)
            self._tabela.setItem(0, 0, item)
            self._tabela.setSpan(0, 0, 1, len(self._COLUNAS))
            self._tabela.setRowHeight(0, 80)
