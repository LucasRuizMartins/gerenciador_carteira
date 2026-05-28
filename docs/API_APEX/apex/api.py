"""
Ponto de entrada único: instancie ApexAPI e acesse os serviços por atributo.
 
Uso:
    from apex import ApexAPI
 
    api = ApexAPI.from_config(cfg_dict)
    dados = api.relatorios.get_extrato(ExtratoParams(...))
"""
 
from .client import ApexAuthClient, ApexHTTPClient
from .config import ApexConfig
from .services import ExtratoParams, FundoService, RelatorioService
 
__all__ = ["ApexAPI", "ExtratoParams"]
 
 
class ApexAPI:
    """
    Fachada principal. Instancie uma vez e reutilize durante toda a execução.
 
    Attributes:
        relatorios: serviços do módulo de relatórios.
        fundos:     serviços do módulo de fundos (extensível).
    """
 
    def __init__(self, config: ApexConfig) -> None:
        auth = ApexAuthClient(config)
        http = ApexHTTPClient(config, auth)
 
        self.relatorios = RelatorioService(http)
        self.fundos = FundoService(http)
 
    @classmethod
    def from_config(cls, cfg: dict) -> "ApexAPI":
        """Constrói a partir de um dicionário de configurações."""
        return cls(ApexConfig.from_dict(cfg))