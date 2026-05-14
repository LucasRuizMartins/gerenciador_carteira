"""
Builder genérico orientado a configuração (config-driven).

O ConfigDrivenBuilder substitui os 15 builders hardcoded de report_builder.py.
Em vez de ter o mapeamento embutido em código Python, ele lê um arquivo JSON
validado pelo schema Pydantic e delega a resolução ao MappingEngine.

Modo de uso:
    from src.services.config_driven_builder import ConfigDrivenBuilder

    # A partir de um arquivo JSON
    builder = ConfigDrivenBuilder.de_arquivo("mapeamentos/ZULU.json")
    mapeamento_cd  = builder.construir_mapeamento_cd(carteira)
    mapeamento_mec = builder.construir_mapeamento_mec(carteira)

    # A partir de um dicionário (útil em testes)
    builder = ConfigDrivenBuilder.de_dict({
        "versao": "1.0",
        "fundo": "TESTE",
        ...
    })

Migração incremental:
    O ConfigDrivenBuilder implementa a mesma interface que ReportBuilderBase,
    permitindo que seja usado no registry.py sem nenhuma alteração no executor.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.logger import get_logger
from src.config.schemas import MapeamentoFundo, ItemMapeamento
from src.services.mapping_engine import MappingEngine, MapeamentoExcel, CustomResolver
from Carteira import CarteiraBase

logger = get_logger(__name__)

# Diretório padrão onde ficam os JSONs de mapeamento
_DIR_MAPEAMENTOS = Path(__file__).resolve().parent.parent.parent / "mapeamentos"


class ConfigDrivenBuilder:
    """Builder genérico que lê mapeamentos de JSON e resolve via MappingEngine.

    Implementa a mesma interface pública de ReportBuilderBase:
        construir_mapeamento_cd(carteira)  -> list[dict]
        construir_mapeamento_mec(carteira) -> list[dict]

    Attributes:
        _config: MapeamentoFundo validado pelo Pydantic.
        _engine: Instância de MappingEngine com resolvers registrados.
    """

    def __init__(self, config: MapeamentoFundo, engine: MappingEngine | None = None) -> None:
        self._config = config
        self._engine = engine or MappingEngine()

    # ------------------------------------------------------------------
    # Construtores alternativos
    # ------------------------------------------------------------------

    @classmethod
    def de_arquivo(cls, path: str | Path) -> "ConfigDrivenBuilder":
        """Cria um builder a partir de um arquivo JSON.

        Args:
            path: Caminho absoluto ou relativo ao JSON.
                  Caminhos relativos são resolvidos a partir do diretório
                  `mapeamentos/` na raiz do projeto.

        Returns:
            ConfigDrivenBuilder instanciado e validado.

        Raises:
            FileNotFoundError: Se o arquivo não existir.
            ValidationError: Se o JSON não for válido segundo o schema.
        """
        path = Path(path)
        if not path.is_absolute():
            path = _DIR_MAPEAMENTOS / path

        if not path.exists():
            raise FileNotFoundError(
                f"Arquivo de mapeamento não encontrado: {path}\n"
                f"Crie o arquivo ou execute a migração dos builders legados."
            )

        logger.info(f"Carregando mapeamento: {path}")
        with path.open(encoding="utf-8") as f:
            dados = json.load(f)

        config = MapeamentoFundo.model_validate(dados)
        return cls(config)

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> "ConfigDrivenBuilder":
        """Cria um builder a partir de um dicionário (útil em testes).

        Args:
            dados: Dicionário com a estrutura de MapeamentoFundo.

        Returns:
            ConfigDrivenBuilder instanciado e validado.
        """
        config = MapeamentoFundo.model_validate(dados)
        return cls(config)

    # ------------------------------------------------------------------
    # Interface pública — compatível com ReportBuilderBase
    # ------------------------------------------------------------------

    def construir_mapeamento_cd(self, carteira: CarteiraBase) -> MapeamentoExcel:
        """Constrói o mapeamento para a aba CD (Carteira Diária).

        Args:
            carteira: Objeto carteira já carregado com carregar_dados().

        Returns:
            MapeamentoExcel: Lista de {"Categoria": str, "Valor": Any}.
        """
        return self._engine.resolver(carteira, self._config.mapeamento_cd)

    def construir_mapeamento_mec(self, carteira: CarteiraBase) -> MapeamentoExcel:
        """Constrói o mapeamento para a aba MEC (Movimentação e Cota).

        Args:
            carteira: Objeto carteira já carregado com carregar_dados().

        Returns:
            MapeamentoExcel: Lista de {"Categoria": str, "Valor": Any}.
        """
        return self._engine.resolver(carteira, self._config.mapeamento_mec)

    # ------------------------------------------------------------------
    # Registro de resolvers custom
    # ------------------------------------------------------------------

    def registrar_custom(self, nome: str, funcao: CustomResolver) -> "ConfigDrivenBuilder":
        """Registra uma função custom no engine e retorna self (fluent API).

        Permite encadear o registro de múltiplas funções:

            builder = (
                ConfigDrivenBuilder.de_arquivo("mapeamentos/AVANTI.json")
                .registrar_custom("calcular_id_rf", calcular_id_rf)
                .registrar_custom("calcular_estoque", calcular_estoque)
            )

        Args:
            nome: Identificador da função (coincide com 'nome_funcao' no JSON).
            funcao: Callable com assinatura (carteira, item) -> Any.

        Returns:
            self (para encadeamento fluente).
        """
        self._engine.register_custom_resolver(nome, funcao)
        return self

    # ------------------------------------------------------------------
    # Propriedades de metadados
    # ------------------------------------------------------------------

    @property
    def fundo(self) -> str:
        return self._config.fundo

    @property
    def administradora(self) -> str:
        return self._config.administradora

    @property
    def versao(self) -> str:
        return self._config.versao

    def __repr__(self) -> str:
        return (
            f"ConfigDrivenBuilder("
            f"fundo={self.fundo!r}, "
            f"admin={self.administradora!r}, "
            f"v={self.versao!r}, "
            f"cd={len(self._config.mapeamento_cd)} itens, "
            f"mec={len(self._config.mapeamento_mec)} itens)"
        )
