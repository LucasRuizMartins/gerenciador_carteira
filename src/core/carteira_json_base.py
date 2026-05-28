from typing import Any
import pandas as pd
from Carteira import CarteiraBase
from src.core.logger import get_logger

logger = get_logger(__name__)

class CarteiraJSONBase(CarteiraBase):
    """
    Base para carteiras processadas a partir de respostas de API / JSON.
    Herda de CarteiraBase para garantir que o MappingEngine e ExcelWriter
    continuem funcionando com a mesma interface (patrimonio_total, dfs, etc).
    """

    def __init__(self, raw_data: dict[str, Any] | None = None) -> None:
        # Não passamos path_carteira, pois a origem agora é a memória (API)
        super().__init__(path_carteira=None)
        self.raw_data = raw_data or {}
        
    def carregar_dados(self, raw_data: dict[str, Any] | None = None) -> None:
        """
        Popula os atributos da carteira a partir do payload JSON.
        Subclasses devem implementar _processar_json() para definir as regras.
        """
        if raw_data is not None:
            self.raw_data = raw_data
            
        if not self.raw_data:
            logger.warning("Nenhum dado JSON fornecido para carregar_dados.")
            return

        # Chama a implementação específica da administradora
        self._processar_json()

    def _processar_planilha(self, aba="CD_ATUAL") -> dict[str, pd.DataFrame]:
        """
        Método herdado que não faz sentido para APIs, mas é exigido pela classe base.
        Retornamos vazio ou levantamos erro lógico.
        """
        return {}

    def _processar_json(self) -> None:
        """
        Extrai os dados de self.raw_data e popula os atributos (pdd, patrimonio_total, dfs).
        Deve ser implementado pela subclasse (ex: CarteiraApexAPI).
        """
        raise NotImplementedError("Subclasses de CarteiraJSONBase devem implementar _processar_json")

    def _json_get(self, path: str, default: Any = 0.0) -> Any:
        """
        Auxiliar para buscar valores em dicionários aninhados usando notação de ponto.
        Ex: _json_get("data.posicaoOutros.posicaoPDD.total.totalValorTotal")
        """
        keys = path.split(".")
        val = self.raw_data
        try:
            for key in keys:
                val = val[key]
            return val
        except (KeyError, TypeError):
            return default
