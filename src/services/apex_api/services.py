from dataclasses import dataclass
from datetime import date
from typing import Any

from .client import ApexHTTPClient


@dataclass
class ExtratoParams:
    doc_fundo: str
    dt_inicio: date
    dt_fim: date

    def to_query(self) -> dict[str, str]:
        return {
            "documentoFundo": self.doc_fundo,
            "dataInicio": self.dt_inicio.strftime("%Y-%m-%d"),
            "dataFim": self.dt_fim.strftime("%Y-%m-%d"),
        }

@dataclass
class ComposicaoCarteiraParams:
    doc_fundo: str
    data: date
    abertura: bool = True
    classe_consolidada: bool = True

    def to_query(self) -> dict[str, str]:
        return {
            "documentoFundo": self.doc_fundo,
            "data": self.data.strftime("%Y-%m-%d"),
            "abertura": "true" if self.abertura else "false",
            "classeConsolidada": "true" if self.classe_consolidada else "false",
        }


class RelatorioService:
    """Serviços relacionados ao módulo de relatórios da Apex."""

    _ENDPOINT_EXTRATO = "/api/relatorios/extrato"
    _ENDPOINT_COMPOSICAO = "/api/relatorios/composicaoCarteira/consolidada"

    def __init__(self, http_client: ApexHTTPClient) -> None:
        self._client = http_client

    def get_extrato(self, params: ExtratoParams) -> Any:
        """
        Retorna o extrato de um fundo para o período informado.

        Args:
            params: instância de ExtratoParams com os filtros desejados.

        Returns:
            dict com os dados retornados pela API.
        """
        return self._client.get(self._ENDPOINT_EXTRATO, params=params.to_query())

    def get_composicao_carteira(self, params: ComposicaoCarteiraParams) -> Any:
        """
        Retorna a composição da carteira de um fundo para a data informada.

        Args:
            params: instância de ComposicaoCarteiraParams com os filtros desejados.

        Returns:
            dict com os dados retornados pela API.
        """
        return self._client.get(self._ENDPOINT_COMPOSICAO, params=params.to_query())


class FundoService:
    """Exemplo de serviço para outros módulos (extensível)."""

    def __init__(self, http_client: ApexHTTPClient) -> None:
        self._client = http_client

    # Adicione novos endpoints aqui seguindo o mesmo padrão