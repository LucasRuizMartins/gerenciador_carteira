"""
MappingEditorPage — editor visual de mapeamentos JSON.
Permite ao usuário editar, validar e salvar os arquivos
mapeamentos/*.json sem abrir código Python.
"""
from __future__ import annotations

import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.gui.viewmodels.mapping_vm import MappingViewModel
from src.gui.widgets.mapping_table import MappingTable
from src.gui.styles import COLORS

import os

class MappingEditorPage(QWidget):
    """
    Página de edição de mapeamentos.

    Layout:
        [Lista de fundos] | [Abas CD / MEC + tabela editável + toolbar]
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = MappingViewModel(self)
        self._fundo_atual: str | None = None
        self._modificado: bool = False
        self._setup_ui()
        self._conectar_vm()
        self._popular_lista()

    # ------------------------------------------------------------------
    # Construção da UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(20)

        # Cabeçalho
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel("Editor de Mapeamentos")
        title.setObjectName("page_title")
        subtitle = QLabel(
            "Edite os mapeamentos JSON sem abrir o código. "
            "As alterações são validadas antes de salvar e versionadas automaticamente."
        )
        subtitle.setObjectName("page_subtitle")
        subtitle.setWordWrap(True)
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        root.addLayout(header)

        # Splitter principal: lista | editor
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # --- Painel esquerdo: lista de fundos ---
        left = QFrame()
        left.setObjectName("card")
        left.setMaximumWidth(220)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)

        search_label = QLabel("Fundos Disponíveis")
        search_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 600;")
        left_layout.addWidget(search_label)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar fundo...")
        self._search.textChanged.connect(self._filtrar_lista)
        left_layout.addWidget(self._search)

        self._lista = QListWidget()
        self._lista.currentItemChanged.connect(self._on_fundo_selecionado)
        left_layout.addWidget(self._lista)

        splitter.addWidget(left)

        # --- Painel direito: editor ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # Toolbar de ações
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._lbl_fundo = QLabel("— Selecione um fundo —")
        self._lbl_fundo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        toolbar.addWidget(self._lbl_fundo)
        toolbar.addStretch()

        self._btn_add    = self._botao("+ Linha",    "btn_ghost", self._add_linha)
        self._btn_rem    = self._botao("- Linha",    "btn_danger", self._rem_linha)
        self._btn_up     = self._botao("↑",          "btn_ghost", lambda: self._mover(-1))
        self._btn_down   = self._botao("↓",          "btn_ghost", lambda: self._mover(+1))
        self._btn_rev    = self._botao("Reverter",   "btn_secondary", self._reverter)
        self._btn_open_dir  = self._botao("📁 Pasta", "btn_secondary", self._abrir_pasta)
        self._btn_open_file = self._botao("📄 Excel", "btn_secondary", self._abrir_arquivo)
        self._btn_save   = self._botao("💾 Salvar",  None, self._salvar)

        for btn in [self._btn_add, self._btn_rem, self._btn_up, self._btn_down,
                    self._btn_rev, self._btn_open_dir, self._btn_open_file, self._btn_save]:
            toolbar.addWidget(btn)
            btn.setEnabled(False)

        right_layout.addLayout(toolbar)

        # Indicador de modificação
        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet(f"color: {COLORS['warning']}; font-size: 11px;")
        right_layout.addWidget(self._lbl_status)

        # Abas CD / MEC
        self._tabs = QTabWidget()
        self._table_cd  = MappingTable()
        self._table_mec = MappingTable()
        self._tabs.addTab(self._table_cd,  "📋 CD (Carteira Diária)")
        self._tabs.addTab(self._table_mec, "📊 MEC (Mecânico)")

        self._table_cd.modificado.connect(self._on_modificado)
        self._table_mec.modificado.connect(self._on_modificado)

        right_layout.addWidget(self._tabs)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

    def _botao(self, label: str, obj_name: str | None, slot) -> QPushButton:
        btn = QPushButton(label)
        if obj_name:
            btn.setObjectName(obj_name)
        btn.clicked.connect(slot)
        return btn

    # ------------------------------------------------------------------
    # Dados
    # ------------------------------------------------------------------

    def _popular_lista(self) -> None:
        self._lista.clear()
        todos = self._vm.todos_os_fundos()
        com_json = set(self._vm.fundos_com_mapeamento())
        for fundo in todos:
            item = QListWidgetItem(fundo)
            if fundo not in com_json:
                item.setForeground(COLORS["text_muted"])
                item.setToolTip("Sem mapeamento JSON — clique para criar")
            self._lista.addItem(item)

    def _filtrar_lista(self, texto: str) -> None:
        for i in range(self._lista.count()):
            item = self._lista.item(i)
            item.setHidden(texto.upper() not in item.text().upper())

    def _conectar_vm(self) -> None:
        self._vm.dados_carregados.connect(self._on_dados_carregados)
        self._vm.salvo.connect(self._on_salvo)
        self._vm.erro.connect(self._on_erro)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_fundo_selecionado(self, current: QListWidgetItem | None, _) -> None:
        if not current:
            return
        if self._modificado:
            resp = QMessageBox.question(
                self,
                "Alterações não salvas",
                "Você tem alterações não salvas. Deseja descartá-las?",
            )
            if resp != QMessageBox.StandardButton.Yes:
                return

        nome = current.text()
        self._fundo_atual = nome
        self._modificado = False
        self._lbl_status.setText("")
        self._vm.carregar(nome)

    def _on_dados_carregados(self, fundo: str, dados: dict) -> None:
        self._lbl_fundo.setText(fundo)
        self._table_cd.carregar(dados.get("mapeamento_cd", []))
        self._table_mec.carregar(dados.get("mapeamento_mec", []))
        self._modificado = False
        self._lbl_status.setText("")

        # Habilita botões de edição
        for btn in [self._btn_add, self._btn_rem, self._btn_up, self._btn_down,
                    self._btn_rev, self._btn_open_dir, self._btn_open_file, self._btn_save]:
            btn.setEnabled(True)

    def _on_modificado(self) -> None:
        if not self._modificado:
            self._modificado = True
            self._lbl_status.setText("● Alterações não salvas")

    def _on_salvo(self, fundo: str) -> None:
        self._modificado = False
        self._lbl_status.setText(f"✔ Salvo com sucesso — {fundo}")
        self._lbl_status.setStyleSheet(f"color: {COLORS['success']}; font-size: 11px;")

    def _on_erro(self, msg: str) -> None:
        QMessageBox.critical(self, "Erro", msg)

    def _add_linha(self) -> None:
        tabela_ativa = self._table_cd if self._tabs.currentIndex() == 0 else self._table_mec
        tabela_ativa.adicionar_linha()

    def _rem_linha(self) -> None:
        tabela_ativa = self._table_cd if self._tabs.currentIndex() == 0 else self._table_mec
        tabela_ativa.remover_linha_selecionada()

    def _mover(self, direcao: int) -> None:
        tabela_ativa = self._table_cd if self._tabs.currentIndex() == 0 else self._table_mec
        tabela_ativa.mover_linha(direcao)

    def _salvar(self) -> None:
        if not self._fundo_atual:
            return
        if not self._table_cd.validar_visual():
            QMessageBox.warning(self, "Validação", "Preencha todas as categorias obrigatórias (marcadas em vermelho).")
            return

        dados_cd  = self._table_cd.exportar()
        dados_mec = self._table_mec.exportar()

        from pathlib import Path
        import json
        path = Path("mapeamentos") / f"{self._fundo_atual}.json"
        if path.exists():
            dados_base = json.loads(path.read_text(encoding="utf-8"))
        else:
            dados_base = self._vm.novo_mapeamento(self._fundo_atual)

        dados_base["mapeamento_cd"]  = dados_cd
        dados_base["mapeamento_mec"] = dados_mec
        self._vm.salvar(self._fundo_atual, dados_base)

        self._lbl_status.setStyleSheet(f"color: {COLORS['success']}; font-size: 11px;")

    def _reverter(self) -> None:
        if not self._fundo_atual:
            return
        backups = self._vm.listar_backups(self._fundo_atual)
        if not backups:
            QMessageBox.information(self, "Reverter", "Nenhum backup disponível para este fundo.")
            return

        # Reverte para o backup mais recente
        ultimo = backups[0]
        resp = QMessageBox.question(
            self,
            "Reverter",
            f"Reverter para:\n{ultimo.name}\n\nA versão atual será salva como backup.",
        )
        if resp == QMessageBox.StandardButton.Yes:
            self._vm.restaurar_backup(self._fundo_atual, ultimo)
            self._vm.carregar(self._fundo_atual)
    def _abrir_pasta(self) -> None:
        if not self._fundo_atual:
            return
        
        caminho = self._vm.obter_caminho_fundo(self._fundo_atual)
        if not caminho:
            QMessageBox.warning(self, "Abrir Pasta", "Não foi possível encontrar o caminho para este fundo no Registro.")
            return
            
        import os
        try:
            os.startfile(caminho)
        except Exception as exc:
            QMessageBox.critical(self, "Erro", f"Não foi possível abrir a pasta:\n{exc}")
    def _abrir_arquivo(self) -> None:
        if not self._fundo_atual:
            return
        
        arquivo = self._vm.obter_arquivo_fundo(self._fundo_atual)
        if not arquivo or not os.path.exists(arquivo):
            QMessageBox.warning(self, "Abrir Excel", f"Arquivo não encontrado ou não configurado:\n{arquivo}")
            return
            
        try:
            os.startfile(arquivo)
        except Exception as exc:
            QMessageBox.critical(self, "Erro", f"Não foi possível abrir o arquivo:\n{exc}")
