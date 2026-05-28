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


class RelatorioService:
    """Serviços relacionados ao módulo de relatórios da Apex."""

    _ENDPOINT_EXTRATO = "/api/relatorios/extrato"

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


class FundoService:
    """Exemplo de serviço para outros módulos (extensível)."""

    def __init__(self, http_client: ApexHTTPClient) -> None:
        self._client = http_client

    # Adicione novos endpoints aqui seguindo o mesmo padrão