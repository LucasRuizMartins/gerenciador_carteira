"""
Serviço de persistência em planilhas Excel via xlwings.

Responsabilidade única: escrever dados em arquivos Excel já existentes.
Toda a lógica de xlwings fica isolada aqui — o resto do sistema não
precisa saber que o backend de persistência é Excel.

Design para extensibilidade (migração futura para banco de dados):
    - O protocolo ``PersistenciaBackend`` define a interface contratual.
    - ``ExcelWriter`` é a implementação atual para Excel/xlwings.
    - Para migrar para PostgreSQL/SQLite, basta criar ``DatabaseWriter``
      implementando o mesmo protocolo — zero alterações nos consumidores.

Uso:
    from src.services.excel_writer import ExcelWriterw

    writer = ExcelWriter()
    writer.salvar_carteira_diaria(
        path_relatorio,
        mapeamento_cd=[{"Categoria": "Data-Base", "Valor": data}],
        mapeamento_mec=[{"Categoria": "DATA", "Valor": data}],
    )
"""

from __future__ import annotations
from src.core.logger import get_logger
logger = get_logger(__name__)

import time
from abc import ABC, abstractmethod
from typing import Protocol

import pandas as pd


# ---------------------------------------------------------------------------
# Protocolo (contrato de interface) — facilita mock em testes e migração futura
# ---------------------------------------------------------------------------


class PersistenciaBackend(Protocol):
    """Contrato de interface para backends de persistência de carteiras.

    Qualquer classe que implemente ``salvar_carteira_diaria`` e
    ``salvar_mapeamento_em_aba`` satisfaz este protocolo automaticamente
    (duck typing estrutural via Protocol).

    Migração para banco de dados:
        Implemente esta interface com INSERT/UPDATE em SQL e substitua
        ``ExcelWriter`` por ``DatabaseWriter`` no registry — sem tocar
        nos builders de relatório.
    """

    def salvar_carteira_diaria(
        self,
        path: str,
        mapeamento_cd: list[dict],
        mapeamento_mec: list[dict],
    ) -> None:
        """Persiste os dados de CD e MEC no arquivo de relatório."""
        ...

    def salvar_mapeamento_em_aba(
        self,
        path: str,
        aba: str,
        mapeamento: list[dict],
    ) -> None:
        """Persiste um único mapeamento em uma aba específica."""
        ...


# ---------------------------------------------------------------------------
# Implementação Excel (backend atual)
# ---------------------------------------------------------------------------


class ExcelWriter:
    """Serviço de escrita de dados em planilhas Excel via xlwings.

    Encapsula toda a lógica de abertura, escrita e salvamento de
    arquivos Excel, garantindo que a instância do xlwings.App seja
    sempre encerrada corretamente (via try/finally).

    Attributes:
        _visible: Se True, a janela do Excel fica visível durante a operação.
            Útil para debugging. Padrão: False.
        _delay_abertura: Segundos de espera após abrir o arquivo para garantir
            que o Excel carregue completamente. Padrão: 1.0s.
    """

    def __init__(
        self,
        visible: bool = False,
        delay_abertura: float = 1.0,
    ) -> None:
        """Inicializa o ExcelWriter.

        Args:
            visible: Exibir a janela do Excel durante a gravação.
            delay_abertura: Tempo de espera (segundos) após abrir o arquivo.
        """
        self._visible = visible
        self._delay_abertura = delay_abertura

    # ------------------------------------------------------------------
    # Interface pública
    # ------------------------------------------------------------------

    def salvar_carteira_diaria(
        self,
        path: str,
        mapeamento_cd: list[dict],
        mapeamento_mec: list[dict],
    ) -> None:
        """Salva os dados de carteira diária nas abas CD e MEC.

        Args:
            path: Caminho absoluto do arquivo Excel de relatório (.xlsb).
            mapeamento_cd: Lista de dicionários ``{"Categoria": ..., "Valor": ...}``
                para a aba CD (Carteira Diária).
            mapeamento_mec: Lista de dicionários ``{"Categoria": ..., "Valor": ...}``
                para a aba MEC (Movimentação e Cota).

        Raises:
            ValueError: Se a aba "CD" ou "MEC" não existir no arquivo.
            RuntimeError: Em caso de falha durante a escrita no Excel.
        """
        import xlwings as xw  # import tardio — xlwings é dependência opcional

        app = xw.App(visible=self._visible)
        try:
            wb = xw.Book(path)
            time.sleep(self._delay_abertura)

            self._verificar_aba(wb, "CD")
            self._verificar_aba(wb, "MEC")

            self._escrever_aba(wb.sheets["CD"], mapeamento_cd)
            self._escrever_aba(wb.sheets["MEC"], mapeamento_mec)

            wb.save()
            logger.info(f"✔ Dados salvos com sucesso em: {path}")

        except Exception as exc:
            raise RuntimeError(
                f"Falha ao salvar dados em '{path}': {exc}"
            ) from exc
        finally:
            app.quit()

    def salvar_mapeamento_em_aba(
        self,
        path: str,
        aba: str,
        mapeamento: list[dict],
    ) -> None:
        """Salva um mapeamento em uma única aba específica.

        Mais flexível que ``salvar_carteira_diaria`` para casos onde
        o relatório possui abas com nomes diferentes de CD/MEC.

        Args:
            path: Caminho absoluto do arquivo Excel.
            aba: Nome da aba de destino.
            mapeamento: Lista de dicionários ``{"Categoria": ..., "Valor": ...}``.

        Raises:
            ValueError: Se a aba não existir no arquivo.
            RuntimeError: Em caso de falha durante a escrita.
        """
        import xlwings as xw

        app = xw.App(visible=self._visible)
        try:
            wb = xw.Book(path)
            time.sleep(self._delay_abertura)
            self._verificar_aba(wb, aba)
            self._escrever_aba(wb.sheets[aba], mapeamento)
            wb.save()
            logger.info(f"✔ Aba '{aba}' salva em: {path}")
        except Exception as exc:
            raise RuntimeError(f"Falha ao salvar aba '{aba}': {exc}") from exc
        finally:
            app.quit()

    def salvar_novos_codigos(
        self,
        path: str,
        novos_codigos: pd.DataFrame,
        nome_planilha: str = "DICIONARIO_CATEGORIA",
    ) -> None:
        """Acrescenta novos códigos ao dicionário de categorias da planilha.

        Args:
            path: Caminho absoluto do arquivo Excel.
            novos_codigos: DataFrame com coluna "Código" contendo os novos códigos.
            nome_planilha: Nome da aba de dicionário. Padrão: "DICIONARIO_CATEGORIA".
        """
        import xlwings as xw

        if novos_codigos.empty:
            return

        app = xw.App(visible=self._visible)
        try:
            wb = xw.Book(path)
            ws = wb.sheets[nome_planilha]
            ultima_linha = ws.range("A" + str(ws.cells.last_cell.row)).end("up").row + 1
            dados = novos_codigos[["Código"]].copy()
            dados["CATEGORIA"] = "VALIDAR"
            ws.range(f"A{ultima_linha}").options(
                index=False, header=False
            ).value = dados.values
            wb.save()
            logger.info(f"✔ {len(novos_codigos)} novo(s) código(s) adicionado(s) ao dicionário.")
        finally:
            app.quit()

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    @staticmethod
    def _verificar_aba(wb: "xw.Book", nome_aba: str) -> None:  # type: ignore[name-defined]
        """Valida que a aba existe na pasta de trabalho.

        Args:
            wb: Pasta de trabalho aberta.
            nome_aba: Nome da aba a verificar.

        Raises:
            ValueError: Se a aba não existir.
        """
        nomes_abas = [sheet.name for sheet in wb.sheets]
        if nome_aba not in nomes_abas:
            raise ValueError(
                f"Aba '{nome_aba}' não encontrada no arquivo. "
                f"Abas disponíveis: {nomes_abas}"
            )

    @staticmethod
    def _escrever_aba(ws: "xw.Sheet", mapeamento: list[dict]) -> None:  # type: ignore[name-defined]
        """Escreve um mapeamento Categoria→Valor na próxima linha disponível da aba.

        Args:
            ws: Aba Excel de destino (objeto xlwings Sheet).
            mapeamento: Lista de dicionários com chaves "Categoria" e "Valor".
        """
        # Encontra a próxima linha vazia robustamente
        ultima_celula = ws.range("C1048576").end("up")
        proxima_linha = ultima_celula.row + 1 if ultima_celula.row != 1 else 1

        # Lê os cabeçalhos das colunas (linha 2)
        ultima_coluna = ws.range("B2").end("right").column

        for col in range(1, ultima_coluna + 1):
            nome_coluna = ws.range(2, col).value
            if not nome_coluna:
                continue
            for item in mapeamento:
                if item.get("Categoria") == nome_coluna:
                    ws.range(proxima_linha, col).value = item["Valor"]
                    break
