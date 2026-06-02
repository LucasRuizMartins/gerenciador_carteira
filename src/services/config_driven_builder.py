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

        # --- Lógica SB_II ---
        def resolver_titulos_sb_ii(c, _):
            titulos_privados = ["DCRED_BRAVYAF", "DCRED_LYSKA", "DCRED_YOU INC"]
            notas_comerciais = [
                "AOI YAMA - 469301683", "BANCO ABC BRASIL 1", "BANCO ABC BRASIL S/A",
                "BANCO SANTANDER SBII", "C165503 CANAA", "C254859 LYSKA", "C259712 LYSKA",
                "C268475 MANCHE", "C310516 NELCARE", "C93998 ANPLA", "CAMPLEZI- 3016793840",
                "NATZAR - 3173879168", "OYA ADVOGADOS", "SABZ ADVOGADOS", "TORTORO E RAGAZZI 1",
                "TORTORO E RAGAZZI AD", "VICE S - 480391069", "VITORIA FIDELIS"
            ]
            df = c.dataframe
            total = 0.0
            try:
                # Títulos Privados (Coluna 10)
                total += df[df["Carteira"].isin(titulos_privados)]["Unnamed: 10"].sum()
                # Notas Comerciais (Coluna 6)
                total += df[df["Carteira"].isin(notas_comerciais)]["Unnamed: 6"].sum()
            except: pass
            return total

        def resolver_outros_valores_sb_ii(c, _):
            cvm = self._engine._resolver_contas(c, FakeItem(filtro='Cvm', dataframe='df_contas_receber_filtrado'))
            contas = self._engine._resolver_contas(c, FakeItem(filtro='Contas a receber', dataframe='df_contas_receber_filtrado'))
            return cvm + contas

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
        reg("resolver_outros_valores_residence", resolver_outros_valores_residence)
        reg("resolver_titulos_sb_ii", resolver_titulos_sb_ii)
        reg("resolver_outros_valores_sb_ii", resolver_outros_valores_sb_ii)

        # --- Lógica AVANTI ---
        def somar_intervalo_avanti(df, inicio, fim, coluna, codigo):
            def to_float_strict(v):
                if hasattr(v, "iloc"): v = v.iloc[0]
                if v is None or (isinstance(v, float) and pd.isna(v)): return 0.0
                try:
                    val = float(v)
                    return 0.0 if pd.isna(val) else val
                except: return 0.0

            total = 0.0
            try:
                # Localiza a linha pelo código na coluna especificada
                linha_dados = df[df[coluna] == codigo].iloc[0]
                # Soma os valores nas posições (colunas) do intervalo
                for i in range(inicio, fim):
                    total += to_float_strict(linha_dados.iloc[i])
            except: pass
            return total

        def resolver_avanti_itambe_estoque(c, _):
            try:
                df_est = pd.read_excel(c.path_carteira, sheet_name="ESTOQUE_ATUAL")
                return df_est[df_est["SEU_NUMERO"] == "U0003360000001"]["VALOR_PRESENTE"].iloc[0]
            except: return 0

        def resolver_avanti_versa_1(c, _):
            try:
                df_est = pd.read_excel(c.path_carteira, sheet_name="ESTOQUE_ATUAL")
                return df_est[df_est["SEU_NUMERO"] == 551995]["VALOR_PRESENTE"].iloc[0]
            except: return 0

        def resolver_avanti_versa_2(c, _):
            try:
                df_est = pd.read_excel(c.path_carteira, sheet_name="ESTOQUE_ATUAL")
                return df_est[df_est["SEU_NUMERO"] == 774293]["VALOR_PRESENTE"].iloc[0]
            except: return 0

        def resolver_avanti_versa_3(c, _):
            try:
                df_est = pd.read_excel(c.path_carteira, sheet_name="ESTOQUE_ATUAL")
                return df_est[df_est["SEU_NUMERO"] == 774294]["VALOR_PRESENTE"].iloc[0]
            except: return 0

        def resolver_avanti_ctr_itambe(c, _): return somar_intervalo_avanti(c.dataframe, 95, 105, "Unnamed: 1", 29690)
        def resolver_avanti_carmel(c, _): return somar_intervalo_avanti(c.dataframe, 90, 105, "Unnamed: 1", "FIDC CARMEL II")
        def resolver_avanti_saldo_tesouraria(c, _): return somar_intervalo_avanti(c.dataframe, 70, 90, "Unnamed: 2", "Total Saldos em Conta Corrente:")
        def resolver_avanti_firf_id(c, _): return somar_intervalo_avanti(c.dataframe, 95, 105, "Unnamed: 1", "FIRF ID SOBERANO")
        def resolver_avanti_id_rf(c, _): return somar_intervalo_avanti(c.dataframe, 80, 95, "Unnamed: 1", "ID RF LP FIC FI")
        def resolver_avanti_santander(c, _): return somar_intervalo_avanti(c.dataframe, 80, 95, "Unnamed: 1", "SAN RF REF DI TITULOS PUB PREMIUM FC FI ")
        def resolver_avanti_patrimonio(c, _): return somar_intervalo_avanti(c.dataframe, 70, 80, "Unnamed: 1", "PATRIMÔNIO FECHAMENTO")
        def resolver_avanti_qtd_cota(c, _): return somar_intervalo_avanti(c.dataframe, 2, 15, "Unnamed: 3", "Qtd. Cotas")
        def resolver_avanti_valor_cota(c, _): return somar_intervalo_avanti(c.dataframe, 45, 63, "Unnamed: 3", "Qtd. Cotas")

        def resolver_avanti_taxa_adm(c, _):
            a_receber_adm = self._engine._resolver_contas(c, FakeItem(filtro="Pagamento de Taxa Administração", dataframe="df_contas_receber")) + \
                            self._engine._resolver_contas(c, FakeItem(filtro="Pagamento taxa de administração", dataframe="df_contas_receber"))
            return c.valor_administracao + a_receber_adm

        def resolver_avanti_taxa_gestao(c, _):
            a_receber_gestao = (self._engine._resolver_contas(c, FakeItem(filtro="Pagamento taxa gestão", dataframe="df_contas_receber")) * -1) + \
                               self._engine._resolver_contas(c, FakeItem(filtro="Pagamento taxa gestão", dataframe="df_contas_pagar"))
            return c.valor_taxa_gestao + a_receber_gestao

        def resolver_avanti_outros_receber(c, _):
            a_receber = 0
            try: a_receber = float(c.dataframe[c.dataframe["Unnamed: 1"] == "PAGAMENTO TAXA ADMINISTRAÇÃO - PAGO A MAIOR "].iloc[0, 81])
            except: pass
            a_receber += self._engine._resolver_contas(c, FakeItem(filtro="amortiz", dataframe="df_contas_receber"))
            return a_receber

        # Registro Avanti
        reg("resolver_avanti_itambe_estoque", resolver_avanti_itambe_estoque)
        reg("resolver_avanti_versa_1", resolver_avanti_versa_1)
        reg("resolver_avanti_versa_2", resolver_avanti_versa_2)
        reg("resolver_avanti_versa_3", resolver_avanti_versa_3)
        reg("resolver_avanti_ctr_itambe", resolver_avanti_ctr_itambe)
        reg("resolver_avanti_carmel", resolver_avanti_carmel)
        reg("resolver_avanti_saldo_tesouraria", resolver_avanti_saldo_tesouraria)
        reg("resolver_avanti_firf_id", resolver_avanti_firf_id)
        reg("resolver_avanti_id_rf", resolver_avanti_id_rf)
        reg("resolver_avanti_santander", resolver_avanti_santander)
        reg("resolver_avanti_patrimonio", resolver_avanti_patrimonio)
        reg("resolver_avanti_qtd_cota", resolver_avanti_qtd_cota)
        reg("resolver_avanti_valor_cota", resolver_avanti_valor_cota)
        reg("resolver_avanti_taxa_adm", resolver_avanti_taxa_adm)
        reg("resolver_avanti_taxa_gestao", resolver_avanti_taxa_gestao)
        reg("resolver_avanti_outros_receber", resolver_avanti_outros_receber)
        
        # Restaurando Residence (acidentalmente removidos)
        reg("resolver_ilha_do_sol_residence", resolver_ilha_do_sol_residence)
        reg("resolver_outras_despesas_residence", resolver_outras_despesas_residence)

        # --- Lógica COBUCCIO ---
        def resolver_cobuccio_soma_secao(c, item):
            return c.somar_coluna_dataframe(item.chave_etl, 'Valor Líquido')

        def resolver_cobuccio_valor_senior(c, _):
            try: return c.df_senior['Valor Bruto'].sum()
            except: return 0.0

        def resolver_cobuccio_senior(c, item):
            try:
                filtro = getattr(item, "filtro", None)
                if not filtro:
                    num = item.categoria.split(" ")[-1]
                    filtro = f"Senior {num}"
                return float(c.df_senior.loc[c.df_senior["CATEGORIA"] == filtro, "PU Mercado"].values[0])
            except: return 0.0

        reg("resolver_cobuccio_soma_secao", resolver_cobuccio_soma_secao)
        reg("resolver_cobuccio_valor_senior", resolver_cobuccio_valor_senior)
        reg("resolver_cobuccio_senior", resolver_cobuccio_senior)

        # --- Lógica SB CREDITO FIDC ---
        def resolver_sb_valor_senior(c, _):
            try: return c.df_senior['Valor Bruto'].sum()
            except: return 0.0

        def resolver_sb_valor_mezanino(c, _):
            try: return c.df_mezanino['Valor Bruto'].sum()
            except: return 0.0

        def resolver_sb_senior(c, item):
            try:
                filtro = getattr(item, "filtro", None)
                if not filtro:
                    filtro = item.categoria
                mask = c.df_senior["CATEGORIA"].str.upper() == filtro.upper()
                return float(c.df_senior.loc[mask, "PU Mercado"].values[0])
            except:
                try:
                    mask = c.df_senior["CATEGORIA"].str.upper() == filtro.upper()
                    return float(c.df_senior.loc[mask, "Pu Mercado"].values[0])
                except: return 0.0

        def resolver_sb_mezanino(c, item):
            try:
                filtro = getattr(item, "filtro", None)
                if not filtro:
                    filtro = item.categoria
                mask = c.df_mezanino["CATEGORIA"].str.upper() == filtro.upper()
                return float(c.df_mezanino.loc[mask, "PU Mercado"].values[0])
            except:
                try:
                    mask = c.df_mezanino["CATEGORIA"].str.upper() == filtro.upper()
                    return float(c.df_mezanino.loc[mask, "Pu Mercado"].values[0])
                except: return 0.0

        reg("resolver_sb_valor_senior", resolver_sb_valor_senior)
        reg("resolver_sb_valor_mezanino", resolver_sb_valor_mezanino)
        reg("resolver_sb_senior", resolver_sb_senior)
        reg("resolver_sb_mezanino", resolver_sb_mezanino)



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
