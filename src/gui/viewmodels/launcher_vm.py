"""
ViewModel para execução de fundos.
Roda processar_fundo_registrado() em QThread separada
e emite sinais de progresso/resultado para a View.
"""
from __future__ import annotations

import os
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from src.core.logger import get_logger

logger = get_logger(__name__)


class _WorkerSignals(QObject):
    iniciando = Signal(str)        # nome_fundo
    sucesso   = Signal(str, float) # nome_fundo, tempo_segundos
    erro      = Signal(str, str)   # nome_fundo, mensagem_erro
    log_line  = Signal(str)        # linha de log em tempo real


class _FundoWorker(QRunnable):
    def __init__(self, nome_fundo: str, aba: str, signals: _WorkerSignals):
        super().__init__()
        self._nome = nome_fundo
        self._aba  = aba
        self.signals = signals
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        import time
        from src.registry import processar_fundo_registrado

        self.signals.iniciando.emit(self._nome)
        start = time.time()
        try:
            processar_fundo_registrado(self._nome, aba=self._aba)
            elapsed = time.time() - start
            self.signals.sucesso.emit(self._nome, elapsed)
        except Exception as exc:
            self.signals.erro.emit(self._nome, str(exc))


class LauncherViewModel(QObject):
    """
    Orquestra a execução de um ou mais fundos em threads separadas.

    Sinais expostos:
        iniciando(nome_fundo)
        sucesso(nome_fundo, segundos)
        erro(nome_fundo, mensagem)
    """

    iniciando = Signal(str)
    sucesso   = Signal(str, float)
    erro      = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(4)
        self._signals = _WorkerSignals()
        # Repassa sinais internos para os externos
        self._signals.iniciando.connect(self.iniciando)
        self._signals.sucesso.connect(self.sucesso)
        self._signals.erro.connect(self.erro)

    def executar(self, nome_fundo: str, aba: str = "CD_ATUAL") -> None:
        """Dispara processamento em thread separada."""
        worker = _FundoWorker(nome_fundo, aba, self._signals)
        self._pool.start(worker)

    def executar_batch(self, fundos_abas: dict[str, str]) -> None:
        """Dispara múltiplos fundos em paralelo (máx 4 simultâneos)."""
        for nome, aba in fundos_abas.items():
            self.executar(nome, aba)

    def fundos_disponiveis(self) -> list[str]:
        from src.registry import REGISTRO
        return list(REGISTRO.keys())
        
    def obter_abas_excel(self, nome_fundo: str) -> list[str]:
        """Retorna a lista de abas reais do arquivo Excel do fundo."""
        try:
            from src.registry import REGISTRO
            from src.config.settings import resolver_path_carteira
            import pandas as pd
            
            config = REGISTRO.get(nome_fundo)
            if not config:
                return ["CD_ATUAL", "MEC_ATUAL"]
            
            path = resolver_path_carteira(config.chave_carteira)
            if not path or not os.path.exists(path):
                return ["CD_ATUAL", "MEC_ATUAL"]
            
            # Lê apenas os nomes das abas (rápido)
            xl = pd.ExcelFile(path)
            return xl.sheet_names[::-1]
        except Exception as exc:
            logger.error(f"Erro ao ler abas de {nome_fundo}: {exc}")
            return ["CD_ATUAL", "MEC_ATUAL"]
