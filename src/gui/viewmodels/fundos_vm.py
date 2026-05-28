"""
FundosViewModel — lógica de negócio para a página de cadastro de fundos.

Responsabilidades:
  1. Listar fundos cadastrados pelo usuário (fundos_api.json).
  2. Adicionar e editar fundos (valida + persiste + atualiza REGISTRO).
  3. Remover fundos.
  4. Testar conexão com a API selecionada para validar o doc_fundo_api.
  5. Fornecer a lista de APIs disponíveis (MAPA_APIS) para a interface.
"""
from __future__ import annotations

from typing import Any
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from src.core.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Worker assíncrono para teste de conexão
# ---------------------------------------------------------------------------

class _TesteConexaoSignals(QObject):
    sucesso = Signal(str, str, str, str)   # (chave, nome_fundo, data_posicao, chave_gerencial)
    erro    = Signal(str)


class _TesteConexaoWorker(QRunnable):
    def __init__(
        self,
        chave: str,
        tipo_api: str,
        doc_fundo_api: str,
        chave_gerencial: str,
        signals: _TesteConexaoSignals,
    ) -> None:
        super().__init__()
        self._chave        = chave
        self._tipo_api     = tipo_api
        self._doc_fundo_api = doc_fundo_api
        self._chave_gerencial = chave_gerencial
        self.signals       = signals
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            from datetime import date, timedelta
            data = date.today() - timedelta(days=1)

            if self._tipo_api == "apex":
                from src.core.carteira_apex_api import CarteiraApexAPI
                carteira = CarteiraApexAPI.criar_da_api(self._doc_fundo_api, data)
                raw = carteira.raw_data
                base = raw.get("data", raw)
                nome = base.get("nomeFundo", self._doc_fundo_api)
                data_pos = str(base.get("dataPosicao", str(data)))
                self.signals.sucesso.emit(self._chave, nome, data_pos, self._chave_gerencial)
            else:
                self.signals.erro.emit(
                    f"Tipo de API '{self._tipo_api}' ainda não implementado."
                )
        except Exception as exc:
            self.signals.erro.emit(str(exc))


# ---------------------------------------------------------------------------
# ViewModel principal
# ---------------------------------------------------------------------------

class FundosViewModel(QObject):
    """
    ViewModel para a página de Fundos Externos (Multi-API).

    Sinais:
        fundos_atualizados(lista_de_dicts)  — lista foi modificada
        conexao_ok(chave, nome_fundo, data_posicao)
        conexao_erro(mensagem)
        salvo(chave)
        removido(chave)
        erro(mensagem)
    """

    fundos_atualizados = Signal(list)
    conexao_ok         = Signal(str, str, str, str)  # (chave, nome_fundo, data_posicao, chave_gerencial)
    conexao_erro       = Signal(str)
    salvo              = Signal(str)
    removido           = Signal(str)
    erro               = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def apis_disponiveis(self) -> list[tuple[str, str]]:
        """Retorna lista de (tipo_api, rotulo) disponíveis."""
        from src.registry import ROTULOS_APIS
        return list(ROTULOS_APIS.items())

    def listar(self) -> list[dict]:
        """Retorna a lista de fundos externos cadastrados."""
        from src.registry import listar_fundos_externos
        return listar_fundos_externos()

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------

    def salvar(self, entry: dict) -> None:
        """
        Salva ou atualiza um fundo no fundos_api.json.

        entry deve conter: chave, nome, tipo_api, doc_fundo_api, chave_gerencial
        """
        from src.registry import salvar_fundo_externo

        chave = entry.get("chave", "").strip()
        if not chave:
            self.erro.emit("A chave do fundo não pode estar vazia.")
            return
        if not entry.get("doc_fundo_api", "").strip():
            self.erro.emit("O identificador da API (ex: CNPJ) não pode estar vazio.")
            return
        if not entry.get("chave_gerencial", "").strip():
            self.erro.emit("A chave gerencial não pode estar vazia.")
            return

        try:
            salvar_fundo_externo(entry)
            self.salvo.emit(chave.upper())
            self.fundos_atualizados.emit(self.listar())
        except Exception as exc:
            self.erro.emit(f"Erro ao salvar fundo: {exc}")

    def remover(self, chave: str) -> None:
        """Remove um fundo do cadastro."""
        from src.registry import remover_fundo_externo
        try:
            remover_fundo_externo(chave)
            self.removido.emit(chave.upper())
            self.fundos_atualizados.emit(self.listar())
        except Exception as exc:
            self.erro.emit(f"Erro ao remover fundo: {exc}")

    # ------------------------------------------------------------------
    # Teste de conexão e mapeamento padrão
    # ------------------------------------------------------------------

    def testar_conexao(self, chave: str, tipo_api: str, doc_fundo_api: str, chave_gerencial: str) -> None:
        """Dispara teste de conexão assíncrono. Emite conexao_ok ou conexao_erro."""
        signals = _TesteConexaoSignals(self)
        signals.sucesso.connect(self.conexao_ok)
        signals.erro.connect(self.conexao_erro)
        worker = _TesteConexaoWorker(chave, tipo_api, doc_fundo_api, chave_gerencial, signals)
        self._pool.start(worker)

    def gerar_mapeamento_padrao(self, chave: str, chave_gerencial: str) -> None:
        """Chama a rotina para criar o JSON de mapeamento com as colunas do CD e MEC."""
        from src.registry import gerar_mapeamento_padrao
        try:
            gerar_mapeamento_padrao(chave, chave_gerencial)
            self.salvo.emit(f"{chave.upper()} (Colunas Mapeadas)")
        except Exception as exc:
            self.erro.emit(f"Erro ao gerar mapeamento padrão: {exc}")
