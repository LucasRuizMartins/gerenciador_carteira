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
import pandas as pd

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
        self._registrar_funcoes_paridade()

    def _registrar_funcoes_paridade(self) -> None:
        """Registra funções para manter paridade com lógicas complexas dos builders legados."""
        
        # --- Helpers para simular itens de mapeamento ---
        class FakeItem:
            def __init__(self, **kwargs):
                for k, v in kwargs.items(): setattr(self, k, v)

        # --- Lógica CDC ---
        def resolver_pdd_cdc(c, _):
            return c.pdd + c.recuperar_valor_carteira("PERDA ESPERADA", 1)
        
        def resolver_outros_valores_cdc(c, _):
            cvm = self._engine._resolver_contas(c, FakeItem(filtro='Cvm', dataframe='df_contas_receber_filtrado'))
            contas = self._engine._resolver_contas(c, FakeItem(filtro='Contas a receber', dataframe='df_contas_receber_filtrado'))
            return cvm + contas

        # --- Lógica CARMEL_II ---
        def resolver_mez_a_carmel_ii(c, _):
            return c.recuperar_valor_carteira("RESIDENCE CLUB FIDC - MEZ A", 5) + \
                   c.recuperar_valor_carteira("FIDC BRL2954 - RESIDENCE CLUB FIDC : FIDC BRL2954 - RESIDENCE CLUB FIDC - MZ A", 5)

        def resolver_mez_b_carmel_ii(c, _):
            return c.recuperar_valor_carteira("RESIDENCE CLUB FIDC - MEZ B", 5) + \
                   c.recuperar_valor_carteira("FIDC BRL2954 - RESIDENCE CLUB FIDC : FIDC BRL2954 - RESIDENCE CLUB FIDC - MZ B", 5)

        def resolver_outras_despesas_carmel_ii(c, _):
            cetip = self._engine._resolver_contas(c, FakeItem(filtro='Cetip', dataframe='df_contas_filtrado'))
            contas = self._engine._resolver_contas(c, FakeItem(filtro='Contas a pagar', dataframe='df_contas_filtrado'))
            return cetip + contas

        # --- Lógica ENEL ---
        def resolver_pdd_enel(c, _):
            return c.recuperar_valor_carteira("PDD", 1) + c.recuperar_valor_carteira("PERDA ESPERADA", 1)

        def resolver_itau_enel(c, _):
            try:
                # Busca direta no dataframe da carteira
                mask = c.dataframe["Carteira"] == "FICFI ITAU SOBERANO RF SIMP LP"
                return c.dataframe.loc[mask].values[0, 5]
            except: return 0

        def resolver_outras_despesas_enel(c, _):
            contas = self._engine._resolver_contas(c, FakeItem(filtro='Contas a pagar', dataframe='df_contas_filtrado'))
            anbima = self._engine._resolver_contas(c, FakeItem(filtro='Anbima', dataframe='df_contas_filtrado'))
            return contas + anbima

        def resolver_outros_valores_enel(c, _):
            anbima = self._engine._resolver_contas(c, FakeItem(filtro='Anbima', dataframe='df_contas_receber_filtrado'))
            cvm = self._engine._resolver_contas(c, FakeItem(filtro='Cvm', dataframe='df_contas_receber_filtrado'))
            contas = self._engine._resolver_contas(c, FakeItem(filtro='Contas a receber', dataframe='df_contas_receber_filtrado'))
            return anbima + cvm + contas

        # --- Lógica MOOVPAY ---
        def resolver_dif_cvm_moovpay(c, _):
            df = c.df_contas_receber
            try: return df[df["Histórico"].str.contains("Cvm", na=False, case=False)]["Valor Total"].sum()
            except: return 0

        def resolver_dif_anbima_moovpay(c, _):
            df = c.df_contas_receber
            try: return df[df["Histórico"].str.contains("Anbima", na=False, case=False)]["Valor Total"].sum()
            except: return 0

        def resolver_banco_liq_moovpay(c, _):
            try:
                mask = c.dataframe["Unnamed: 2"].str.contains("banco liquidante", case=False, na=False)
                return float(c.dataframe.loc[mask, "Unnamed: 4"].iloc[0])
            except: return 0

        def resolver_outros_receber_moovpay(c, _):
            dif_cvm = resolver_dif_cvm_moovpay(c, None)
            return c.outros_valores_receber - dif_cvm

        def resolver_outras_despesas_moovpay(c, _):
            banco_liq = resolver_banco_liq_moovpay(c, None)
            return c.outros_valores_pagar - banco_liq

        # --- Lógica RESIDENCE ---
        def resolver_ilha_do_sol_residence(c, _):
            return sum(c.recuperar_valor_carteira(f"NC_ILHADOSOL{suffix}", 10) 
                       for suffix in ["", "_2T", "_3T", "_4T", "_5T", "_6T", "_7T", "_8T", "_9T", "_10T"])

        def resolver_outras_despesas_residence(c, _):
            cvm = self._engine._resolver_contas(c, FakeItem(filtro='Cvm', dataframe='df_contas_filtrado'))
            return c.outros_valores_pagar + cvm

        def resolver_outros_valores_residence(c, _):
            contas = self._engine._resolver_contas(c, FakeItem(filtro='Contas a receber', dataframe='df_contas_receber_filtrado'))
            gestao = self._engine._resolver_contas(c, FakeItem(filtro='Gestão', dataframe='df_contas_receber_filtrado'))
            return contas + gestao

        # Registro em lote no motor
        reg = self.registrar_custom
        reg("resolver_pdd_cdc", resolver_pdd_cdc)
        reg("resolver_outros_valores_cdc", resolver_outros_valores_cdc)
        reg("resolver_mez_a_carmel_ii", resolver_mez_a_carmel_ii)
        reg("resolver_mez_b_carmel_ii", resolver_mez_b_carmel_ii)
        reg("resolver_outras_despesas_carmel_ii", resolver_outras_despesas_carmel_ii)
        reg("resolver_pdd_enel", resolver_pdd_enel)
        reg("resolver_itau_enel", resolver_itau_enel)
        reg("resolver_outras_despesas_enel", resolver_outras_despesas_enel)
        reg("resolver_outros_valores_enel", resolver_outros_valores_enel)
        reg("resolver_dif_cvm_moovpay", resolver_dif_cvm_moovpay)
        reg("resolver_dif_anbima_moovpay", resolver_dif_anbima_moovpay)
        reg("resolver_banco_liq_moovpay", resolver_banco_liq_moovpay)
        reg("resolver_outros_receber_moovpay", resolver_outros_receber_moovpay)
        reg("resolver_outras_despesas_moovpay", resolver_outras_despesas_moovpay)
        reg("resolver_ilha_do_sol_residence", resolver_ilha_do_sol_residence)
        reg("resolver_outras_despesas_residence", resolver_outras_despesas_residence)
        reg("resolver_outros_valores_residence", resolver_outros_valores_residence)

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
