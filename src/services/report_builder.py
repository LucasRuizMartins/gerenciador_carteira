"""
Builders de mapeamentos CD/MEC para cada fundo gerido pela Carmel Capital.

Cada builder é uma classe com responsabilidade única: construir as listas
de mapeamento ``{"Categoria": ..., "Valor": ...}`` para as abas CD e MEC
de um fundo específico, dado o objeto carteira já carregado.

Design:
    - ``ReportBuilderBase`` define o contrato (ABC).
    - Cada fundo tem seu próprio builder (SRP).
    - Builders recebem o objeto carteira por injeção de dependência (DIP).
    - Nenhum builder sabe nada sobre Excel/DB — apenas monta dicionários.

Extensibilidade:
    - Ao adicionar um novo fundo, crie um novo builder sem alterar os existentes (OCP).
    - Se a fonte de dados mudar (Excel → DB), os builders permanecem intactos.

Uso:
    from src.services.report_builder import FidaraReportBuilder
    from Carteira import CarteiraBRL

    carteira = CarteiraBRL(path)
    carteira.carregar_dados()

    builder = FidaraReportBuilder()
    mapeamento_cd  = builder.construir_mapeamento_cd(carteira)
    mapeamento_mec = builder.construir_mapeamento_mec(carteira)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from Carteira import CarteiraBRL, CarteiraBase


# ---------------------------------------------------------------------------
# Tipo auxiliar
# ---------------------------------------------------------------------------

MapeamentoExcel = list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Classe base abstrata
# ---------------------------------------------------------------------------


class ReportBuilderBase(ABC):
    """Contrato para construtores de mapeamentos de relatório.

    Todo builder deve implementar ``construir_mapeamento_cd`` e
    ``construir_mapeamento_mec``, retornando listas de dicionários
    prontas para serem escritas pelo ``ExcelWriter``.
    """

    @abstractmethod
    def construir_mapeamento_cd(self, carteira: CarteiraBase) -> MapeamentoExcel:
        """Constrói o mapeamento para a aba CD (Carteira Diária).

        Args:
            carteira: Objeto carteira já carregado com ``carregar_dados()``.

        Returns:
            MapeamentoExcel: Lista de ``{"Categoria": str, "Valor": Any}``.
        """

    @abstractmethod
    def construir_mapeamento_mec(self, carteira: CarteiraBase) -> MapeamentoExcel:
        """Constrói o mapeamento para a aba MEC (Movimentação e Cota).

        Args:
            carteira: Objeto carteira já carregado com ``carregar_dados()``.

        Returns:
            MapeamentoExcel: Lista de ``{"Categoria": str, "Valor": Any}``.
        """

    # ------------------------------------------------------------------
    # Helpers compartilhados entre builders
    # ------------------------------------------------------------------

    @staticmethod
    def _item(categoria: str, valor: Any) -> dict[str, Any]:
        """Atalho para criar um item de mapeamento.

        Args:
            categoria: Nome da categoria na planilha.
            valor: Valor a inserir.

        Returns:
            dict: ``{"Categoria": categoria, "Valor": valor}``.
        """
        return {"Categoria": categoria, "Valor": valor}

    @staticmethod
    def _parsear_cota(valor: Any) -> float:
        """Converte o valor de cota retornado pela carteira para float.

        Trata casos onde o valor é string com formatação brasileira.

        Args:
            valor: Valor bruto da cota (str ou numérico).

        Returns:
            float: Valor convertido. Retorna 0.0 em caso de erro.
        """
        if valor is None:
            return 0.0
        try:
            if isinstance(valor, str):
                return float(valor.replace(".", "").replace(",", "."))
            return float(valor)
        except (ValueError, TypeError):
            return 0.0


# ---------------------------------------------------------------------------
# Builder: FIDARA FIDC
# ---------------------------------------------------------------------------


class FidaraReportBuilder(ReportBuilderBase):
    """Constrói os mapeamentos de relatório para o FIDARA FIDC.

    Administradora: BRL (CarteiraBRL)
    """

    def construir_mapeamento_cd(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        """Mapeamento da aba CD do FIDARA FIDC.

        Args:
            carteira: Carteira BRL do FIDARA já carregada.

        Returns:
            MapeamentoExcel: Mapeamento completo da aba CD.
        """
        i = self._item
        return [
            i("Data-Base",                                    carteira.data),
            i("Direitos Creditórios a Vencer",                carteira.recuperar_valor_carteira("A VENCER", 2)),
            i("Direitos Creditórios Vencidos",                carteira.recuperar_valor_carteira("VENCIDO", 2)),
            i("Direitos Creditórios - Nota Comercial",        0),
            i("Direitos Creditórios Vencidos - Debenture",    0),
            i("Direitos Creditórios Vencidos - Juros s/ Deb", 0),
            i("PDD - Prov. de Perdas",                        carteira.recuperar_valor_carteira("PDD", 1)),
            i("GV Cash RF DI",                                carteira.recuperar_valor_carteira("GV CASH RENDA FIXA REFERENCIADO DI LONGO PRAZO FUNDO DE INVESTIMENTO", 5)),
            i("FIF RF BRL REF DI LP",                         carteira.recuperar_valor_carteira("FI BRL1200 - FIF RF BRL REF DI LP", 5)),
            i("NTN-B",                                        carteira.recuperar_valor_carteira("NTNB20600815 - 760199", 10)),
            i("Saldo em Tesouraria",                          carteira.saldo_tesouraria),
            i("Over/Compromissada",                           0),
            i("Senior (-)",                                   0),
            i("Mezanino (-)",                                 0),
            i("Taxa de Administração",                        carteira.valor_administracao),
            i("Taxa de Custódia",                             carteira.valor_taxa_custodia),
            i("Taxa de Gestão",                               carteira.valor_taxa_gestao),
            i("Taxa de Auditoria",                            carteira.valor_taxa_auditoria),
            i("Despesa CVM - Diferimento",                    0),
            i("Dif. Despesa Fisc. CVM",                       carteira.valor_taxa_cvm),
            i("Taxa ANBIMA",                                  carteira.valor_anbima),
            i("Taxa de Performance",                          carteira.valor_taxa_performance),
            i("Outros valores a receber  (+)",                carteira.outros_valores_receber),
            i("Outras despesas  (-)",                         carteira.outros_valores_pagar),
            i("Despesa CVM",                                  0),
            i("Despesa ANBIMA",                               carteira.valor_anbima),
            i("Taxa Fisc. CVM",                               carteira.recuperar_contas("Cvm", carteira.df_contas_filtrado)),
            i("Resgate/Amortização de Cotas (-)",             0),
            i("PL Carteira Subordinada Digitar",              carteira.patrimonio_total),
            i("Dif. de despesa ANBIMA",                       0),
            i("Diferimento de despesa  CVM ",                 0),
            i("TAXA SELIC",                                   0),
            i("TAXA CETIP",                                   0),
            i("Banco Liquidante",                             0),
        ]

    def construir_mapeamento_mec(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        """Mapeamento da aba MEC do FIDARA FIDC.

        Args:
            carteira: Carteira BRL do FIDARA já carregada.

        Returns:
            MapeamentoExcel: Mapeamento completo da aba MEC.
        """
        i = self._item
        cota_sub = self._parsear_cota(carteira.recuperar_valor_carteira("Valor da Cota Líquida", 1))
        qtd_cotas = carteira.recuperar_valor_carteira("Qtde. Cota", 1)
        return [
            i("DATA",                  carteira.data),
            i("VALOR DE APLICAÇÃO",    0),
            i("VALOR DE RESGATE",      0),
            i("COTAS RESGATADAS",      0),
            i("COTAS EMITIDAS",        0),
            i("VALOR DE RESGATE ",     0),
            i("QUANT COTAS",           qtd_cotas),
            i("VALOR DA COTA",         cota_sub),
            i("AMORTIZ. DIA",          0),
            i("TOTAL DE SUBSCRIÇÃO",   0),
        ]


# ---------------------------------------------------------------------------
# Builder: CDC EMPRESTIMOS FIDC
# ---------------------------------------------------------------------------


class CdcReportBuilder(ReportBuilderBase):
    """Constrói os mapeamentos de relatório para o CDC EMPRESTIMOS FIDC.

    Administradora: BRL (CarteiraBRL)
    """

    # Ordens das cotas sênior e mezanino no DataFrame de cotas superiores
    _ORDENS_SENIOR = [99, 98, 97, 96, 95, 93]
    _ORDEM_MEZANINO = 94

    def construir_mapeamento_cd(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        df_cotas = carteira.df_cotas_superiores
        from carteira_apex import obter_valor_ordem

        valor_senior = sum(
            obter_valor_ordem(df_cotas, o, "Valor Total")
            for o in self._ORDENS_SENIOR
        )
        valor_mezanino = obter_valor_ordem(df_cotas, self._ORDEM_MEZANINO, "Valor Total")
        perda_esperada = carteira.recuperar_valor_carteira("PERDA ESPERADA", 1)

        return [
            i("Data-Base",                               carteira.data),
            i("Direitos Creditórios a Vencer",           carteira.a_vencer),
            i("Direitos Creditórios Vencidos",           carteira.vencido),
            i("PDD - Prov. de Perdas",                   carteira.pdd + perda_esperada),
            i("Saldo em Tesouraria",                     carteira.saldo_tesouraria),
            i("BRL FI DI LP",                            carteira.valor_di),
            i("Taxa de Administração",                   carteira.valor_administracao),
            i("Taxa de Custódia",                        carteira.valor_taxa_custodia),
            i("Taxa de Gestão",                          carteira.valor_taxa_gestao),
            i("Despesa de Auditoria",                    carteira.valor_taxa_auditoria),
            i("Taxa Anbima (-)",                         carteira.recuperar_contas("Anbima", carteira.df_contas_filtrado)),
            i("Taxa de Performance",                     0),
            i("Outras despesas operacionais (-)",        carteira.recuperar_contas("Contas a pagar", carteira.df_contas_filtrado)),
            i("Taxa Fisc. CVM",                          carteira.valor_taxa_cvm),
            i("Diferimento de Taxa ANBIMA",              carteira.recuperar_contas("Anbima", carteira.df_contas_receber_filtrado)),
            i("Outros valores  (+)",                     carteira.recuperar_contas("Cvm", carteira.df_contas_receber_filtrado) + carteira.recuperar_contas("Contas a receber", carteira.df_contas_receber_filtrado)),
            i("Senior (-)",                              valor_senior * -1),
            i("Mezanino (-)",                            valor_mezanino * -1),
            i("Títulos Públicos",                        0),
            i("PL Carteira Subordinada",                 carteira.patrimonio_total),
        ]

    def construir_mapeamento_mec(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        from carteira_apex import obter_valor_ordem
        df_cotas = carteira.df_cotas_superiores

        cota_sub = self._parsear_cota(carteira.recuperar_valor_carteira("Valor da Cota Líquida", 1))
        qtd_sub = carteira.recuperar_valor_carteira("Qtde. Cota", 1)

        return [
            i("DATA",                      carteira.data),
            i("VALOR DE APLICAÇÃO SUBORDINADA", 0),
            i("COTAS EMITIDAS SUBORDINADA", 0),
            i("VALOR DE RESGATE SUBORDINADA", 0),
            i("QUANT COTAS SUBORDINADA",   qtd_sub),
            i("VALOR DA COTA SUBORDINADA", cota_sub),
            i("AMORTIZ. DIA SUBORDINADA",  0),
            i("VALOR DE APLICAÇÃO MEZANINO", 0),
            i("VALOR DE RESGATE MEZANINO", 0),
            i("COTAS RESGATADAS MEZANINO", 0),
            i("QUANT COTAS MEZANINO",      obter_valor_ordem(df_cotas, self._ORDEM_MEZANINO, "Qtde. Total")),
            i("VALOR DA COTA - MEZANINO",  obter_valor_ordem(df_cotas, self._ORDEM_MEZANINO, "Valor Cota")),
            i("AMORTIZ. DIA MEZANINO",     0),
            i("VALOR DE APLICAÇÃO SENIOR", 0),
            i("COTAS EMITIDAS SENIOR",     0),
            i("VALOR DE RESGATE SENIOR",   0),
            i("COTAS RESGATADAS SENIOR",   0),
            i("QUANT COTAS SENIOR",        obter_valor_ordem(df_cotas, 98, "Qtde. Total")),
            i("VALOR DA COTA - SENIOR",    obter_valor_ordem(df_cotas, 98, "Valor Cota")),
            i("AMORTIZ. DIA SENIOR",       0),
            i("QUANT COTAS SENIOR 3",      obter_valor_ordem(df_cotas, 97, "Qtde. Total")),
            i("VALOR DA COTA - SENIOR 3",  obter_valor_ordem(df_cotas, 97, "Valor Cota")),
            i("AMORTIZ. DIA SENIOR 3",     0),
            i("QUANT COTAS SENIOR 4",      obter_valor_ordem(df_cotas, 96, "Qtde. Total")),
            i("VALOR DA COTA - SENIOR 4",  obter_valor_ordem(df_cotas, 96, "Valor Cota")),
            i("AMORTIZ. DIA SENIOR 4",     0),
            i("QUANT COTAS SENIOR 5",      obter_valor_ordem(df_cotas, 95, "Qtde. Total")),
            i("VALOR DA COTA - SENIOR 5",  obter_valor_ordem(df_cotas, 95, "Valor Cota")),
            i("AMORTIZ. DIA SENIOR 5",     0),
            i("QUANT COTAS SENIOR 6",      obter_valor_ordem(df_cotas, 93, "Qtde. Total")),
            i("VALOR DA COTA - SENIOR 6",  obter_valor_ordem(df_cotas, 93, "Valor Cota")),
            i("AMORTIZ. DIA SENIOR 6",     0),
            i("QUANT COTAS SENIOR 7",      0),
            i("VALOR DA COTA - SENIOR 7",  0),
            i("AMORTIZ. DIA SENIOR 7",     0),
        ]


# ---------------------------------------------------------------------------
# Builder: CARMEL II FIDC
# ---------------------------------------------------------------------------


class CarmelIIReportBuilder(ReportBuilderBase):
    """Constrói os mapeamentos de relatório para o CARMEL II FIDC.

    Administradora: BRL (CarteiraBRL)
    """

    def construir_mapeamento_cd(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        return [
            i("Data-Base",                                    carteira.data),
            i("Residence Club - Senior 3",                    carteira.recuperar_valor_carteira("FIDC BRL2954 - RESIDENCE CLUB FIDC : FIDC BRL2954 - RESIDENCE CLUB FIDC - SR 03", 5)),
            i("Residence Club - Mezanino A",                  carteira.recuperar_valor_carteira("RESIDENCE CLUB FIDC - MEZ A", 5) + carteira.recuperar_valor_carteira("FIDC BRL2954 - RESIDENCE CLUB FIDC : FIDC BRL2954 - RESIDENCE CLUB FIDC - MZ A", 5)),
            i("Residence Club - Mezanino B2",                 carteira.recuperar_valor_carteira("RESIDENCE CLUB FIDC - MEZ B", 5) + carteira.recuperar_valor_carteira("FIDC BRL2954 - RESIDENCE CLUB FIDC : FIDC BRL2954 - RESIDENCE CLUB FIDC - MZ B", 5)),
            i("CDC - Sênior",                                 carteira.recuperar_valor_carteira("FIDC BRL2830 - CDC EMPRESTIMOS FIDC DE CLASSE ÚNICA FECHADA SEN", 5)),
            i("SB Crédito - Mezanino H",                      carteira.recuperar_valor_carteira("SB CREDITO FIDC MULTISETORIAL MEZ H", 5)),
            i("SB Crédito - Mezanino D",                      0),
            i("Carmel FIC FIDC",                              carteira.recuperar_valor_carteira("CARMEL FIC FIDC", 5)),
            i("Direitos Creditórios a Vencer - NC Moovpay",   carteira.recuperar_valor_carteira("Total NC-PRÉ:", 10)),
            i("CRI REIT",                                     carteira.recuperar_valor_carteira("CRI_25B2384188", 10)),
            i("BRL FIRF DI LP",                               carteira.valor_di),
            i("NTN-B ",                                       carteira.recuperar_valor_carteira("NTNB20600815 - 760199", 10)),
            i("Taxa de Administração",                        carteira.valor_administracao),
            i("Taxa de Gestão",                               carteira.valor_taxa_gestao),
            i("Taxa de Auditoria",                            carteira.valor_taxa_auditoria),
            i("Taxa Fisc. CVM",                               carteira.valor_taxa_cvm),
            i("Taxa ANBIMA",                                  carteira.recuperar_contas("Anbima", carteira.df_contas_filtrado)),
            i("Outras despesas  (-)",                         carteira.recuperar_contas("Cetip", carteira.df_contas_filtrado) + carteira.recuperar_contas("Contas a pagar", carteira.df_contas_filtrado)),
            i("Dif. de despesa CVM ",                         carteira.recuperar_contas("Cvm", carteira.df_contas_receber_filtrado)),
            i("Dif. de despesa ANBIMA",                       carteira.recuperar_contas("Anbima", carteira.df_contas_receber_filtrado)),
            i("Outros valores a receber  (+)",                carteira.recuperar_contas("Contas a receber", carteira.df_contas_receber_filtrado)),
            i("Senior (-)",                                   0),
            i("Mezanino (-)",                                 0),
            i("PL Carteira Subordinada",                      carteira.patrimonio_total),
        ]

    def construir_mapeamento_mec(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        cota_sub = self._parsear_cota(carteira.recuperar_valor_carteira("Valor da Cota Líquida", 1))
        qtd_sub = carteira.recuperar_valor_carteira("Qtde. Cota", 1)
        return [
            i("DATA",                              carteira.data),
            i("VALOR DE APLICAÇÃO",                0),
            i("COTAS EMITIDAS",                    0),
            i("VALOR DE RESGATE ",                 0),
            i("COTAS RESGATADAS",                  0),
            i("QUANT COTAS",                       qtd_sub),
            i("VALOR DA COTA CARMEL II FIDC",      cota_sub),
            i("AMORTIZ. DIA",                      0),
        ]


# ---------------------------------------------------------------------------
# Builder: GERAR CAPITAL FIDC
# ---------------------------------------------------------------------------


class GerarReportBuilder(ReportBuilderBase):
    """Constrói os mapeamentos de relatório para o GERAR CAPITAL FIDC.

    Administradora: BRL (CarteiraBRL)
    """

    def construir_mapeamento_cd(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        cota_mezanino = carteira.recuperar_valor_carteira("99", 5)
        cota_senior = carteira.recuperar_valor_carteira("98", 5)
        
        cota_mezanino = cota_mezanino * -1 if cota_mezanino else 0
        cota_senior = cota_senior * -1 if cota_senior else 0

        return [
            i("Data-Base",                                     carteira.data),
            i("Direitos Creditórios a Vencer",                 carteira.recuperar_valor_carteira("A VENCER", 2)),
            i("Direitos Creditórios Vencidos",                 carteira.recuperar_valor_carteira("VENCIDO", 2)),
            i("PDD - Prov. de Perdas",                         carteira.recuperar_valor_carteira("PDD", 1)),
            i("Saldo em Tesouraria",                           carteira.saldo_tesouraria),
            i("GV Cash RF DI LP",                              carteira.recuperar_valor_carteira("GV CASH RENDA FIXA REFERENCIADO DI LONGO PRAZO FUNDO DE INVESTIMENTO", 5)),
            i("FIF RENDA FIXA BRL SOBERANO RF DI",             carteira.recuperar_valor_carteira("FIF BRL2314 - FIF RENDA FIXA BRL SOBERANO REFERENCIADO DI LONGO PRAZO", 5)),
            i("NTN-B",                                         carteira.recuperar_valor_carteira("NTNB20600815 - 760199", 10)),
            i("Taxa de Administração",                         carteira.valor_administracao),
            i("Taxa de Consultoria",                           carteira.recuperar_contas("Consultoria", carteira.df_contas_filtrado)),
            i("Taxa de Custódia",                              carteira.recuperar_contas("Custódia", carteira.df_contas_filtrado)),
            i("Taxa de Gestão",                                carteira.valor_taxa_gestao),
            i("Taxa ANBIMA",                                   carteira.valor_anbima),
            i("Taxa de Auditoria",                             carteira.valor_taxa_auditoria),
            i("Movimento/Custódia",                            0),
            i("Outras despesas  (-)",                          carteira.outros_valores_pagar),
            i("Amortização a Pagar (-)",                       0),
            i("Taxa Fisc. CVM",                                carteira.valor_taxa_cvm),
            i("Dif. Despesa Fisc. ANBIMA",                     carteira.recuperar_contas("Anbima", carteira.df_contas_receber_filtrado)),
            i("Dif. Despesa Fisc. CVM",                        carteira.recuperar_contas("Cvm", carteira.df_contas_receber_filtrado)),
            i("Cobrança (d+1) ",                               0),
            i("Outros valores a receber  (+)",                 carteira.outros_valores_receber),
            i("Senior (-)",                                    cota_senior),
            i("Mezanino (-)",                                  cota_mezanino),
            i("PL Carteira Subordinada",                       carteira.patrimonio_total),
            i("Razão de Garantia Exigida",                     0.5),
            i("Relação Mínima (Sub Jr x Meza)",                0.3),
            i("Recebíveis em Processamento",                   0),
            i("Saldo Conta de Arrecação",                      0),
            i("TAXA SELIC",                                    carteira.recuperar_contas("Selic", carteira.df_contas_filtrado)),
            i("TAXA CETIP",                                    0),
            i("Banco Liquidante",                              carteira.recuperar_contas("Banco Liquidante", carteira.df_contas_filtrado)),
        ]

    def construir_mapeamento_mec(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        from carteira_apex import obter_valor_ordem
        df_cotas = carteira.df_cotas_superiores
        cota_sub = self._parsear_cota(carteira.recuperar_valor_carteira("Valor da Cota Líquida", 1))
        qtd_sub = carteira.recuperar_valor_carteira("Qtde. Cota", 1)

        return [
            i("DATA",                                 carteira.data),
            i("VALOR DE APLICAÇÃO SUBORDINADA",       0),
            i("VALOR DE RESGATE SUBORDINADA",         0),
            i("QUANT COTAS SUBORDINADA",              qtd_sub),
            i("VALOR DA COTA SUBORDINADA",            cota_sub),
            i("AMORTIZ. DIA SUBORDINADA",             0),
            i("TOTAL DE SUBSCRIÇÃO SUBORDINADA",      0),
            i("VALOR DE APLICAÇÃO MEZANINO A",        0),
            i("VALOR DE RESGATE MEZANINO A",          0),
            i("COTAS RESGATADAS MEZANINO A",          0),
            i("QUANT COTAS MEZANINO A",               obter_valor_ordem(df_cotas, 99, "Qtde. Total")),
            i("VALOR COTA MEZANINO A",                obter_valor_ordem(df_cotas, 99, "Valor Cota")),
            i("AMORTIZ. DIA MEZANINO A",              0),
            i("VALOR DE APLICAÇÃO SENIOR",            0),
            i("COTAS RESGATADAS SENIOR",              0),
            i("VALOR DE RESGATE SENIOR",              0),
            i("QUANT COTAS SENIOR",                   obter_valor_ordem(df_cotas, 98, "Qtde. Total")),
            i("VALOR COTA SENIOR",                    obter_valor_ordem(df_cotas, 98, "Valor Cota")),
            i("AMORTIZ. DIA SENIOR",                  0),
            i("TOTAL DE SUBSCRIÇÃO SENIOR",           0),
        ]


# ---------------------------------------------------------------------------
# Builder: ENEL II FIDC
# ---------------------------------------------------------------------------


class EnelReportBuilder(ReportBuilderBase):
    """Constrói os mapeamentos de relatório para o ENEL II FIDC.

    Administradora: BRL (CarteiraBRL)
    """

    def construir_mapeamento_cd(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        from carteira_apex import obter_valor_ordem
        df_cotas = carteira.df_cotas_superiores
        valor_senior = obter_valor_ordem(df_cotas, 99, "Valor Total")
        
        try:
            itau = carteira.dataframe.loc[carteira.dataframe["Carteira"] == "FICFI ITAU SOBERANO RF SIMP LP"].values[0, 5]
        except (IndexError, KeyError):
            itau = 0

        pdd = carteira.recuperar_valor_carteira("PDD", 1)
        perda_esperada = carteira.recuperar_valor_carteira("PERDA ESPERADA", 1)
        
        contas_pagar = carteira.recuperar_contas("Contas a pagar", carteira.df_contas_filtrado)
        anbima = carteira.recuperar_contas("Anbima", carteira.df_contas_filtrado)

        return [
            i("Data-Base",                               carteira.data),
            i("Direitos Creditórios a Vencer",           carteira.a_vencer),
            i("Direitos Creditórios Vencidos",           carteira.vencido),
            i("PDD - Prov. de Perdas",                   pdd + perda_esperada),
            i("Saldo em Tesouraria",                     carteira.saldo_tesouraria),
            i("FICFI Itaú Soberano RF Simples RF",       itau),
            i("BRL FI DI LP",                            carteira.valor_di),
            i("Taxa de Administração",                   carteira.valor_administracao),
            i("Taxa de Custódia",                        carteira.valor_taxa_custodia),
            i("Taxa de Consultoria",                     carteira.recuperar_contas("Consultoria", carteira.df_contas_filtrado)),
            i("Taxa de Gestão",                          carteira.valor_taxa_gestao),
            i("Taxa de Auditoria",                       carteira.valor_taxa_auditoria),
            i("Taxa ANBIMA",                             0),
            i("Taxa de Performance",                     0),
            i("Outras despesas  (-)",                    contas_pagar + anbima),
            i("Taxa Fisc. CVM",                          carteira.valor_taxa_cvm),
            i("Diferimento de Taxa ANBIMA",              0),
            i("Dif. Despesa Fisc. CVM",                  0),
            i("Dif. Despesa Fisc. ANBIMA",               0),
            i("Outros valores a receber  (+)",           carteira.recuperar_contas("Anbima", carteira.df_contas_receber_filtrado) + carteira.recuperar_contas("Cvm", carteira.df_contas_receber_filtrado) + carteira.recuperar_contas("Contas a receber", carteira.df_contas_receber_filtrado)),
            i("Senior (-)",                              valor_senior * -1),
            i("Mezanino (-)",                            0),
            i("Títulos Públicos",                        0),
            i("PL Carteira Subordinada - Digitar",       carteira.patrimonio_total),
        ]

    def construir_mapeamento_mec(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        from carteira_apex import obter_valor_ordem
        df_cotas = carteira.df_cotas_superiores
        cota_sub = self._parsear_cota(carteira.recuperar_valor_carteira("Valor da Cota Líquida", 1))
        qtd_sub = carteira.recuperar_valor_carteira("Qtde. Cota", 1)

        return [
            i("DATA",                                 carteira.data),
            i("VALOR DE APLICAÇÃO SUBORDINADA",       0),
            i("COTAS EMITIDAS SUBORDINADA",           0),
            i("VALOR DE RESGATE SUBORDINADA",         0),
            i("QUANT COTAS SUBORDINADA",              qtd_sub),
            i("VALOR DA COTA SUBORDINADA",            cota_sub),
            i("AMORTIZ. DIA SUBORDINADA",             0),
            i("VALOR DE APLICAÇÃO MEZANINO",          0),
            i("VALOR DE RESGATE MEZANINO",            0),
            i("COTAS RESGATADAS MEZANINO",            0),
            i("QUANT COTAS MEZANINO",                 0),
            i("VALOR DA COTA - MEZANINO",             0),
            i("AMORTIZ. DIA MEZANINO",                0),
            i("VALOR DE APLICAÇÃO SENIOR",            0),
            i("COTAS EMITIDAS SENIOR",                0),
            i("VALOR DE RESGATE SENIOR",              0),
            i("COTAS RESGATADAS SENIOR",              0),
            i("QUANT COTAS SENIOR",                   obter_valor_ordem(df_cotas, 99, "Qtde. Total")),
            i("VALOR DA COTA - SENIOR",               obter_valor_ordem(df_cotas, 99, "Valor Cota")),
            i("AMORTIZ. DIA SENIOR",                  0),
        ]


# ---------------------------------------------------------------------------
# Builder: HOUSI FIDC
# ---------------------------------------------------------------------------


class HousiReportBuilder(ReportBuilderBase):
    """Constrói os mapeamentos de relatório para o HOUSI FIDC.

    Administradora: BRL (CarteiraBRL)
    """

    def construir_mapeamento_cd(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        from carteira_apex import obter_valor_ordem
        df_cotas = carteira.df_cotas_superiores
        valor_senior = obter_valor_ordem(df_cotas, 99, "Valor Total")

        return [
            i("Data-Base",                               carteira.data),
            i("Direitos Creditórios a Vencer",           carteira.a_vencer),
            i("Direitos Creditórios Vencidos",           carteira.vencido),
            i("PDD - Prov. de Perdas",                   carteira.pdd),
            i("Saldo em Tesouraria",                     carteira.saldo_tesouraria),
            i("BRL TRUST DTVM S/A",                      carteira.valor_di),
            i("Taxa de Administração",                   carteira.valor_administracao),
            i("Taxa de Custódia",                        carteira.valor_taxa_custodia),
            i("Taxa de Consultoria",                     carteira.recuperar_contas("Taxa de consultoria", carteira.df_contas_filtrado)),
            i("Taxa de Gestão",                          carteira.valor_taxa_gestao),
            i("Taxa de Auditoria",                       carteira.valor_taxa_auditoria),
            i("Taxa ANBIMA",                             carteira.recuperar_contas("Anbima", carteira.df_contas_filtrado)),
            i("Taxa Fisc. CVM",                          carteira.valor_taxa_cvm),
            i("Taxa de Performance",                     0),
            i("Outras despesas  (-)",                    carteira.outros_valores_pagar),
            i("Dif. de despesa CVM ",                    carteira.recuperar_contas("Cvm", carteira.df_contas_receber_filtrado)),
            i("Dif. de despesa ANBIMA",                  carteira.recuperar_contas("Anbima", carteira.df_contas_receber_filtrado)),
            i("Outros valores a receber  (+)",           carteira.outros_valores_receber),
            i("Ajuste de Compensação de Cotas",          0),
            i("Senior (-)",                              valor_senior * -1),
            i("Mezanino (-)",                            0),
            i("Títulos Públicos",                        0),
            i("PL Carteira Subordinada Digitar",         carteira.patrimonio_total),
            i("Subordinação Mínima",                     0.1),
        ]

    def construir_mapeamento_mec(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        from carteira_apex import obter_valor_ordem
        df_cotas = carteira.df_cotas_superiores
        cota_sub = self._parsear_cota(carteira.recuperar_valor_carteira("Valor da Cota Líquida", 1))
        qtd_sub = carteira.recuperar_valor_carteira("Qtde. Cota", 1)

        return [
            i("DATA",                                 carteira.data),
            i("VALOR DE APLICAÇÃO SUBORDINADA",       0),
            i("COTAS EMITIDAS SUBORDINADA",           0),
            i("VALOR DE RESGATE SUBORDINADA",         0),
            i("QUANT COTAS SUBORDINADA",              qtd_sub),
            i("VALOR DA COTA SUBORDINADA",            cota_sub),
            i("AMORTIZ. DIA SUBORDINADA",             0),
            i("VALOR DE APLICAÇÃO SENIOR",            0),
            i("COTAS EMITIDAS SENIOR",                0),
            i("VALOR DE RESGATE SENIOR",              0),
            i("COTAS RESGATADAS SENIOR",              0),
            i("QUANT COTAS SENIOR",                   obter_valor_ordem(df_cotas, 99, "Qtde. Total")),
            i("VALOR DA COTA - SENIOR",               obter_valor_ordem(df_cotas, 99, "Valor Cota")),
            i("AMORTIZ. DIA SENIOR",                  0),
            i("VALOR DE APLICAÇÃO MEZANINO",          0),
            i("COTAS EMITIDAS MEZANINO",              0),
            i("VALOR DE RESGATE MEZANINO",            0),
            i("COTAS RESGATADAS MEZANINO",            0),
            i("QUANT COTAS MEZANINO",                 0),
            i("VALOR DA COTA - MEZANINO",             0),
            i("AMORTIZ. DIA MEZANINO",                0),
            i("SUBORDINAÇÃO MÍNIMA EXIGIDA",          0),
        ]


# ---------------------------------------------------------------------------
# Builder: INFRA PORTFOLIO I
# ---------------------------------------------------------------------------


class InfraReportBuilder(ReportBuilderBase):
    """Constrói os mapeamentos de relatório para o INFRA PORTFOLIO I.

    Administradora: BRL (CarteiraBRL)
    """

    def construir_mapeamento_cd(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item

        return [
            i("Data-Base",                              carteira.data),
            i("Belluno - Senior 2",                     0),
            i("Infra Setorial FIP Multiestregia",       carteira.recuperar_valor_carteira("INFRA SETORIAL FIP", 5)),
            i("Saldo em Tesouraria",                    carteira.saldo_tesouraria),
            i("CONASA",                                 carteira.recuperar_valor_carteira("CONASA S.A.", 8)),
            i("LFT",                                    carteira.recuperar_valor_carteira("LFT20290901 - 210100", 10)),
            i("Itaú Soberano",                          0),
            i("RJI Cash FI RF",                         0),
            i("Carmel FIC de FIDC",                     0),
            i("BRADESCO",                               carteira.recuperar_valor_carteira("CORPORATE RF SIMPLES", 5)),
            i("NTN-B",                                  0),
            i("PL Carteira  Digitar",                   carteira.patrimonio_total),
            i("Taxa de Administração",                  carteira.valor_administracao),
            i("Taxa de Custódia",                       carteira.valor_taxa_custodia),
            i("Taxa de Gestão",                         carteira.valor_taxa_gestao),
            i("Taxa de Auditoria",                      carteira.valor_taxa_auditoria),
            i("Taxa Fisc. CVM",                         carteira.valor_taxa_cvm),
            i("Taxa ANBIMA",                            0),
            i("Outras despesas  (-)",                   carteira.recuperar_contas("Cetip", carteira.df_contas_filtrado)),
            i("Dif. de despesa CVM ",                   carteira.recuperar_contas("Cvm", carteira.df_contas_filtrado)),
            i("Dif. de despesa ANBIMA",                 0),
            i("Outros valores a receber  (+)",          0),
            i("PL Cotas Seniores",                      0),
        ]

    def construir_mapeamento_mec(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        cota_sub = self._parsear_cota(carteira.recuperar_valor_carteira("Valor da Cota Líquida", 1))
        qtd_sub = carteira.recuperar_valor_carteira("Qtde. Cota", 1)

        return [
            i("DATA",                                 carteira.data),
            i("VALOR DE APLICAÇÃO",                   0),
            i("COTAS EMITIDAS",                       0),
            i("VALOR DE RESGATE ",                    0),
            i("COTAS RESGATADAS",                     0),
            i("QUANT COTAS",                          qtd_sub),
            i("VALOR DA COTA INFRA PREVIDÊNCIA",      cota_sub),
            i("AMORTIZ. DIA",                         0),
        ]


# ---------------------------------------------------------------------------
# Builder: MOOVPAY
# ---------------------------------------------------------------------------


class MoovpayReportBuilder(ReportBuilderBase):
    """Constrói os mapeamentos de relatório para o MOOVPAY.

    Administradora: BRL (CarteiraBRL)
    """

    def construir_mapeamento_cd(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        from carteira_apex import limpar_valor

        df = carteira.df_contas_receber
        try:
            dif_cvm = df[df["Histórico"].str.contains("Cvm", na=False, case=False)]["Valor Total"].sum()
        except (KeyError, ValueError):
            dif_cvm = 0

        try:
            dif_anbima = df[df["Histórico"].str.contains("Anbima", na=False, case=False)]["Valor Total"].sum()
        except (KeyError, ValueError):
            dif_anbima = 0

        try:
            mascara = carteira.dataframe["Unnamed: 2"].str.contains("banco liquidante", case=False, na=False)
            valor_liq_banco = float(carteira.dataframe.loc[mascara, "Unnamed: 4"].iloc[0])
        except (KeyError, IndexError, ValueError):
            valor_liq_banco = 0

        df_cotas = carteira.df_cotas_superiores
        from carteira_apex import obter_valor_ordem
        valor_senior = obter_valor_ordem(df_cotas, 98, "Valor Total")
        valor_mezan = obter_valor_ordem(df_cotas, 99, "Valor Total")

        return [
            i("Data-Base",                                carteira.data),
            i("Direitos Creditórios a Vencer",            carteira.recuperar_valor_carteira("A VENCER", 2)),
            i("Direitos Creditórios Vencidos",            carteira.recuperar_valor_carteira("VENCIDO", 2)),
            i("Direitos Creditórios c/ Nota Comercial",   carteira.recuperar_valor_carteira("Total NC-PRÉ:", 10)),
            i("Fortitudine FIC FIDC",                     0),
            i("PDD - Prov. de Perdas",                    carteira.recuperar_valor_carteira("PDD", 1)),
            i("BRIT FIDC NP",                             carteira.recuperar_valor_carteira("BRIT FUNDO DE INVESTIMENTO EM DIREITOS CREDITÓRIOS", 5)),
            i("GV Cash RF DI LP",                         carteira.valor_di),
            i("NTN-B",                                    carteira.recuperar_valor_carteira("NTNB20600815 - 760199", 10)),
            i("Saldo em Tesouraria",                      carteira.saldo_tesouraria),
            i("Senior (-)",                               valor_senior * -1),
            i("Mezanino (-)",                             valor_mezan * -1),
            i("Taxa de Administração",                    carteira.valor_administracao),
            i("Taxa de Custódia",                         carteira.valor_taxa_custodia),
            i("Taxa de Gestão",                           carteira.valor_taxa_gestao),
            i("Despesa de Auditoria",                     carteira.valor_taxa_auditoria),
            i("Despesa CVM - Diferimento",                dif_cvm),
            i("Taxa ANBIMA - Diferimento",                dif_anbima),
            i("Taxa de Performance",                      carteira.recuperar_contas("Performance", carteira.df_contas_filtrado)),
            i("Outros Valores a Receber",                 carteira.outros_valores_receber - dif_cvm),
            i("Outras despesas  (-)",                     carteira.outros_valores_pagar - valor_liq_banco),
            i("PL Carteira Subordinada",                  carteira.patrimonio_total),
            i("Despesa CVM",                              carteira.recuperar_contas("Cvm", carteira.df_contas_filtrado)),
            i("Despesa ANBIMA",                           carteira.recuperar_contas("Anbima", carteira.df_contas_filtrado)),
            i("TAXA SELIC",                               carteira.recuperar_contas("Selic", carteira.df_contas_filtrado)),
            i("TAXA CETIP",                               carteira.recuperar_contas("Cetip", carteira.df_contas_filtrado)),
            i("Banco Liquidante",                         valor_liq_banco),
        ]

    def construir_mapeamento_mec(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        from carteira_apex import obter_valor_ordem
        df_cotas = carteira.df_cotas_superiores

        cota_sub = self._parsear_cota(carteira.recuperar_valor_carteira("Valor da Cota Líquida", 1))
        qtd_sub = carteira.recuperar_valor_carteira("Qtde. Cota", 1)

        qtd_cota_senior_4 = obter_valor_ordem(df_cotas, 98, "Qtde. Total")
        valor_senior_4 = obter_valor_ordem(df_cotas, 98, "Valor Cota")
        qtd_cota_mezan_1 = obter_valor_ordem(df_cotas, 99, "Qtde. Total")
        valor_mezan_1 = obter_valor_ordem(df_cotas, 99, "Valor Cota")

        return [
            i("DATA",                        carteira.data),
            i("VALOR DE APLICAÇÃO",          0),
            i("VALOR DE RESGATE",            0),
            i("AMORTIZ. DIA",                0),
            i("QUANT COTAS SUB",             qtd_sub),
            i("COTA SUBORDINADA",            cota_sub),
            i("VALOR DE APLICAÇÃO MEZANINO A", 0),
            i("VALOR DE RESGATE MEZANINO A",   0),
            i("QUANT COTAS (MEZANINO)",      0),
            i("COTA MEZANINO A",             0),
            i("AMORTIZ. DIA MEZANINO",       0),
            i("VALOR DE APLICAÇÃO MEZANINO 1", 0),
            i("VALOR DE RESGATE MEZANINO 1",   0),
            i("QUANT COTAS MEZANINO 1",      qtd_cota_mezan_1),
            i("COTA MEZANINO 1",             valor_mezan_1),
            i("AMORTIZ. DIA  MEZANINO 1",    0),
            i("VALOR DE APLICAÇÃO SENIOR 1", 0),
            i("VALOR DE RESGATE SENIOR 1",   0),
            i("QUANT COTAS SENIOR 1",        0),
            i("COTA SENIOR 1",               0),
            i("AMORTIZ. DIA SENIOR 1",       0),
            i("RETORNO DIARIO SENIOR 1",     0),
            i("VALOR DE APLICAÇÃO SENIOR 2", 0),
            i("VALOR DE APLICAÇÃO SENIOR 3", 0),
            i("VALOR DE RESGATE SENIOR 3",   0),
            i("QUANT COTAS SENIOR 3",        0),
            i("VALOR DA COTA - SENIOR 3",    0),
            i("AMORTIZ. DIA  SENIOR 3",      0),
            i("VALOR DE APLICAÇÃO SENIOR 4", 0),
            i("VALOR DE RESGATE SENIOR 4",   0),
            i("QUANT COTAS SENIOR 4",        qtd_cota_senior_4),
            i("COTA SENIOR 4",               valor_senior_4),
            i("AMORTIZ. DIA SENIOR 4",       0),
        ]


# ---------------------------------------------------------------------------
# Builder: RESIDENCE CLUB FIDC
# ---------------------------------------------------------------------------


class ResidenceReportBuilder(ReportBuilderBase):
    """Constrói os mapeamentos de relatório para o RESIDENCE CLUB FIDC."""

    def construir_mapeamento_cd(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item

        ilha_do_sol = (
            carteira.recuperar_valor_carteira("NC_ILHADOSOL", 10) +
            carteira.recuperar_valor_carteira("NC_ILHADOSOL_2T", 10) +
            carteira.recuperar_valor_carteira("NC_ILHADOSOL_3T", 10) +
            carteira.recuperar_valor_carteira("NC_ILHADOSOL_4T", 10) +
            carteira.recuperar_valor_carteira("NC_ILHADOSOL_5T", 10) +
            carteira.recuperar_valor_carteira("NC_ILHADOSOL_6T", 10) +
            carteira.recuperar_valor_carteira("NC_ILHADOSOL_7T", 10) +
            carteira.recuperar_valor_carteira("NC_ILHADOSOL_8T", 10) +
            carteira.recuperar_valor_carteira("NC_ILHADOSOL_9T", 10) +
            carteira.recuperar_valor_carteira("NC_ILHADOSOL_10T", 10)
        )

        df_cotas = carteira.df_cotas_superiores
        from carteira_apex import obter_valor_ordem
        valor_mezanino = obter_valor_ordem(df_cotas, 96, "Valor Total") + obter_valor_ordem(df_cotas, 97, "Valor Total")
        valor_senior = obter_valor_ordem(df_cotas, 98, "Valor Total") + obter_valor_ordem(df_cotas, 99, "Valor Total")

        return [
            i("Data-Base",                                carteira.data),
            i("Direitos Creditórios a Vencer",            carteira.recuperar_valor_carteira("A VENCER", 2)),
            i("Direitos Creditórios Vencidos",            carteira.recuperar_valor_carteira("VENCIDO", 2)),
            i("PDD - Prov. de Perdas",                    carteira.recuperar_valor_carteira("PDD", 1)),
            i("Saldo em Tesouraria",                      carteira.saldo_tesouraria),
            i("Over/Compromissada",                       0),
            i("GV Cash RF DI LP",                         carteira.recuperar_valor_carteira("GV CASH RENDA FIXA REFERENCIADO DI LONGO PRAZO FUNDO DE INVESTIMENTO", 5)),
            i("FIF BRL DI",                               carteira.recuperar_valor_carteira("FIF BRL2314 - FIF RENDA FIXA BRL SOBERANO REFERENCIADO DI LONGO PRAZO", 5)),
            i("FIF RF BRL REF DI LP",                     carteira.recuperar_valor_carteira("FI BRL1200 - FIF RF BRL REF DI LP", 5)),
            i("NTN-B",                                    carteira.recuperar_valor_carteira("Total NTN-PÓS:", 10)),
            i("Ilha do Sol",                              ilha_do_sol),
            i("Taxa de Administração",                    carteira.valor_administracao),
            i("Taxa de Custódia",                         carteira.valor_taxa_custodia),
            i("Taxa de Consultoria",                      carteira.recuperar_contas("Consultoria", carteira.df_contas_filtrado)),
            i("Taxa de Gestão",                           carteira.valor_taxa_gestao),
            i("Taxa ANBIMA",                              carteira.recuperar_contas("Anbima", carteira.df_contas_filtrado)),
            i("Taxa de Auditoria",                        carteira.valor_taxa_auditoria),
            i("Movimento/Custódia",                       0),
            i("Taxa CETIP",                               carteira.recuperar_contas("Cetip", carteira.df_contas_filtrado)),
            i("Outros Valores a Pagar (-)",               carteira.outros_valores_pagar + carteira.recuperar_contas("Cvm", carteira.df_contas_filtrado)),
            i("Amortização a Pagar (-)",                  0),
            i("Diferimento de despesa  CVM ",             carteira.recuperar_contas("Cvm", carteira.df_contas_receber_filtrado)),
            i("Dif. de despesa ANBIMA",                   carteira.recuperar_contas("Anbima", carteira.df_contas_receber_filtrado)),
            i("Dif. de Despesa de Rating",                0),
            i("Cobrança (d+1) ",                          0),
            i("Outros Valores (+)",                       carteira.recuperar_contas("Contas a receber", carteira.df_contas_receber_filtrado) + carteira.recuperar_contas("Gestão", carteira.df_contas_receber_filtrado)),
            i("Cota Senior 1 (-)",                        valor_senior * -1),
            i("Cota Senior 2 (-)",                        0),
            i("Mezanino (-)",                             valor_mezanino * -1),
            i("PL da Carteira",                           carteira.patrimonio_total),
            i("Razão de Garantia Exigida",                0.5),
            i("Relação Mínima (Sub Jr x Meza)",           0.3),
            i("Recebíveis em Processamento",              0),
            i("Saldo Conta de Arrecação",                 0),
            i("Taxa Selic",                               carteira.recuperar_contas("Selic", carteira.df_contas_filtrado)),
            i("Banco Liquidante",                         carteira.recuperar_contas("Banco Liquidante", carteira.df_contas_filtrado)),
        ]

    def construir_mapeamento_mec(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        from carteira_apex import obter_valor_ordem
        df_cotas = carteira.df_cotas_superiores

        cota_sub = self._parsear_cota(carteira.recuperar_valor_carteira("Valor da Cota Líquida", 1))
        qtd_sub = carteira.recuperar_valor_carteira("Qtde. Cota", 1)

        return [
            i("DATA",                                 carteira.data),
            i("VALOR DE APLICAÇÃO SUBORDINADA",       0),
            i("VALOR DE RESGATE SUBORDINADA",         0),
            i("QUANT COTAS SUBORDINADA",              qtd_sub),
            i("VALOR COTA SUBORDINADA",               cota_sub),
            i("AMORTIZ. DIA SUBORDINADA",             0),
            i("VALOR DE APLICAÇÃO MEZANINO A",        0),
            i("VALOR DE RESGATE MEZANINO A",          0),
            i("COTAS RESGATADAS MEZANINO A",          0),
            i("QUANT COTAS MEZANINO A",               obter_valor_ordem(df_cotas, 97, "Qtde. Total")),
            i("VALOR COTA MEZANINO A",                obter_valor_ordem(df_cotas, 97, "Valor Cota")),
            i("AMORTIZ. DIA MEZANINO A",              0),
            i("VALOR DE APLICAÇÃO MEZANINO B",        0),
            i("QUANT COTAS MEZANINO B",               obter_valor_ordem(df_cotas, 96, "Qtde. Total")),
            i("VALOR DE RESGATE MEZANINO B",          0),
            i("VALOR COTA MEZANINO B",                obter_valor_ordem(df_cotas, 96, "Valor Cota")),
            i("AMORTIZ. DIA MEZANINO B",              0),
            i("VALOR DE APLICAÇÃO SENIOR 1",          0),
            i("VALOR DE RESGATE SENIOR 1",            0),
            i("VALOR COTA SENIOR 1",                  obter_valor_ordem(df_cotas, 99, "Valor Cota")),
            i("QUANT COTAS SENIOR 1",                 obter_valor_ordem(df_cotas, 99, "Qtde. Total")),
            i("AMORTIZ. DIA SENIOR 1",                0),
            i("VALOR DE APLICAÇÃO SENIOR 2",          0),
            i("VALOR COTA SENIOR 2",                  0.0000001),
            i("VALOR DE RESGATE SENIOR 2",            0),
            i("QUANT COTAS SENIOR 2",                 0),
            i("AMORTIZ. DIA SENIOR 2",                0),
            i("VALOR COTA SENIO 2",                   0.0000001),
            i("VALOR DE APLICAÇÃO SENIOR 3",          0),
            i("VALOR DE RESGATE  SENIOR 3",           0),
            i("QUANT COTAS SENIOR 3",                 obter_valor_ordem(df_cotas, 98, "Qtde. Total")),
            i("VALOR COTA SENIOR 3",                  obter_valor_ordem(df_cotas, 98, "Valor Cota")),
            i("AMORTIZ. DIA SENIOR 3",                0),
            i("% SUBORDINAÇÃO SÊNIOR",                0.5),
            i("APORTE DE SENIOR (PREVISTO D+1)",      0),
            i("APORTE DE SUBORDINADA (PREVISTO D+1)", 0),
        ]


# ---------------------------------------------------------------------------
# Builder: SB MULTIESTRATEGIA II
# ---------------------------------------------------------------------------


class SbIIReportBuilder(ReportBuilderBase):
    """Constrói os mapeamentos de relatório para o SB MULTIESTRATEGIA II."""

    def construir_mapeamento_cd(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        from carteira_apex import obter_valor_ordem
        import pandas as pd
        import os

        # Leitura dinâmica do arquivo de códigos auxiliares (com suporte a expansão de ~ ou uso de os.environ)
        # Usa o mesmo path hardcoded no script original, mas adaptado
        user_profile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
        path_codigos = os.path.join(
            user_profile,
            r"Carmel Capital\Arquivos - Documentos\00 - CARMEL ASSET\01 - OPERACIONAL\CONTROLADORIA\01 - Relatorios Diarios\Carteira Diaria\Fundos Ativos\SB MULTIESTRATEGIA II\codigos_renda_fixa.xlsx"
        )

        direito_cred_venc = 0
        try:
            lista_renda_fixa = pd.read_excel(path_codigos, sheet_name="TITULOS_PRIVADOS")
            lista_clientes = pd.read_excel(path_codigos, sheet_name="NOTA_COMERCIAL")
            
            codigos_renda_fixa = lista_renda_fixa["CÓDIGO"].tolist()
            codigos_lista_clientes = lista_clientes["CÓDIGO"].tolist()
            
            df = carteira.dataframe
            direito_cred_venc += df[df["Carteira"].isin(codigos_renda_fixa)]["Unnamed: 10"].sum()
            direito_cred_venc += df[df["Carteira"].isin(codigos_lista_clientes)]["Unnamed: 6"].sum()
        except Exception:
            pass

        df_cotas = carteira.df_cotas_superiores
        valor_senior = obter_valor_ordem(df_cotas, 99, "Valor Total")
        valor_mezanino = obter_valor_ordem(df_cotas, 98, "Valor Total")

        return [
            i("Data-Base",                               carteira.data),
            i("Direitos Creditórios a Vencer",           carteira.a_vencer),
            i("Direitos Creditórios Vencidos",           carteira.vencido),
            i("PDD - Prov. de Perdas",                   carteira.pdd),
            i("Direitos Creditórios Vencidos - NPL",     direito_cred_venc),
            i("Saldo em Tesouraria",                     carteira.saldo_tesouraria),
            i("BRL RF REF DI LP FI",                     carteira.valor_di),
            i("SB FIC FIDC - SUB",                       carteira.recuperar_valor_carteira("SB FIC FIDC SUBORDINADA", 5)),
            i("Taxa de Administração",                   carteira.valor_administracao),
            i("Taxa de Custódia",                        carteira.valor_taxa_custodia),
            i("Taxa Consultoria",                        carteira.recuperar_contas("Consultoria", carteira.df_contas_filtrado)),
            i("Taxa de Gestão",                          carteira.valor_taxa_gestao),
            i("TAXA CVM",                                carteira.valor_taxa_cvm),
            i("Despesa de Auditoria",                    carteira.valor_taxa_auditoria),
            i("Taxa Anbima (-)",                         carteira.recuperar_contas("Anbima", carteira.df_contas_filtrado)),
            i("Taxa de Performance",                     carteira.recuperar_contas("Performance", carteira.df_contas_filtrado)),
            i("TAXA SELIC",                              0),
            i("TAXA CETIP",                              carteira.recuperar_contas("Cetip", carteira.df_contas_filtrado)),
            i("Banco Liquidante",                        0),
            i("Outras despesas operacionais (-)",        carteira.recuperar_contas("Contas a pagar", carteira.df_contas_filtrado)),
            i("Diferimento de Taxa ANBIMA",              carteira.recuperar_contas("Anbima", carteira.df_contas_receber_filtrado)),
            i("Outros valores  (+)",                     carteira.recuperar_contas("Cvm", carteira.df_contas_receber_filtrado) + carteira.recuperar_contas("Contas a receber", carteira.df_contas_receber_filtrado)),
            i("Senior (-)",                              valor_senior * -1),
            i("Mezanino (-)",                            valor_mezanino * -1),
            i("PL Carteira Subordinada",                 carteira.patrimonio_total),
            i("Títulos Públicos",                        0),
        ]

    def construir_mapeamento_mec(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        from carteira_apex import obter_valor_ordem
        df_cotas = carteira.df_cotas_superiores

        cota_sub = self._parsear_cota(carteira.recuperar_valor_carteira("Valor da Cota Líquida", 1))

        return [
            i("DATA",                                 carteira.data),
            i("VALOR DE APLICAÇÃO SUBORDINADA",       0),
            i("VALOR DE RESGATE SUBORDINADA",         0),
            i("VALOR COTA SUBORDINADA",               cota_sub),
            i("AMORTIZ. DIA SUBORDINADA",             0),
            i("VALOR DE APLICAÇÃO SENIOR",            0),
            i("VALOR DE RESGATE SENIOR",              0),
            i("VALOR COTA SENIOR",                    obter_valor_ordem(df_cotas, 99, "Valor Cota")),
            i("AMORTIZ. DIA SENIOR",                  0),
            i("VALOR DE APLICAÇÃO MEZANINO",          0),
            i("VALOR DE RESGATE MEZANINO",            0),
            i("VALOR COTA MEZANINO",                  obter_valor_ordem(df_cotas, 98, "Valor Cota")),
            i("AMORTIZ. DIA MEZANINO",                0),
        ]


# ---------------------------------------------------------------------------
# Builder: ZULU FIP
# ---------------------------------------------------------------------------


class ZuluReportBuilder(ReportBuilderBase):
    """Constrói os mapeamentos de relatório para o ZULU FIP."""

    def construir_mapeamento_cd(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        return [
            i("Data-Base",                               carteira.data),
            i("GRUPO MPR PARTICIPACOES S.A.",            carteira.recuperar_valor_carteira("GRUPO MPR PARTICIP", 8)),
            i("Saldo em Tesouraria",                     carteira.saldo_tesouraria),
            i("FI BRL1200 - FI RF BRL REF DI LP",        carteira.valor_di),
            i("Taxa de Administração",                   carteira.valor_administracao),
            i("Taxa de Custódia",                        carteira.valor_taxa_custodia),
            i("Taxa de Gestão",                          carteira.valor_taxa_gestao),
            i("Taxa de Auditoria",                       carteira.valor_taxa_auditoria),
            i("Taxa Fisc. CVM",                          carteira.valor_taxa_cvm),
            i("Taxa ANBIMA",                             carteira.recuperar_contas("Anbima", carteira.df_contas_filtrado)),
            i("Taxa de Performance",                     0),
            i("Outras despesas  (-)",                    carteira.recuperar_contas("Contas a pagar", carteira.df_contas_filtrado)),
            i("Dif. de despesa CVM ",                    carteira.recuperar_contas("Cvm", carteira.df_contas_receber_filtrado)),
            i("Dif. de despesa ANBIMA",                  carteira.recuperar_contas("Anbima", carteira.df_contas_receber_filtrado)),
            i("Outros valores a receber  (+)",           carteira.recuperar_contas("Contas a receber", carteira.df_contas_receber_filtrado)),
            i("Ajuste de Compensação de Cotas",          0),
            i("Senior (-)",                              0),
            i("Mezanino (-)",                            0),
            i("PL Carteira Subordinada Digitar",         carteira.patrimonio_total),
            i("Subordinação Mínima",                     0.1),
            i("Títulos Públicos",                        0),
        ]

    def construir_mapeamento_mec(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        cota_sub = self._parsear_cota(carteira.recuperar_valor_carteira("Valor da Cota Líquida", 1))
        qtd_sub = carteira.recuperar_valor_carteira("Qtde. Cota", 1)

        return [
            i("DATA",                                 carteira.data),
            i("VALOR DE APLICAÇÃO",                   0),
            i("COTAS EMITIDAS",                       0),
            i("VALOR DE RESGATE ",                    0),
            i("COTAS RESGATADAS",                     0),
            i("QUANT COTAS",                          qtd_sub),
            i("VALOR DA COTA",                        cota_sub),
            i("AMORTIZ. DIA",                         0),
            i("VALOR DE APLICAÇÃO SENIOR",            0),
            i("COTAS EMITIDAS SENIOR",                0),
            i("VALOR DE RESGATE SENIOR",              0),
            i("QUANT COTAS SENIOR",                   0),
            i("VALOR DA COTA - SENIOR",               0),
            i("AMORTIZ. DIA SENIOR",                  0),
        ]


# ---------------------------------------------------------------------------
# Builder: VIRTUS CAPITAL
# ---------------------------------------------------------------------------


class VirtusReportBuilder(ReportBuilderBase):
    """Constrói os mapeamentos de relatório para o VIRTUS CAPITAL."""

    def construir_mapeamento_cd(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        from carteira_apex import obter_valor_ordem
        df_cotas = carteira.df_cotas_superiores

        valor_senior = obter_valor_ordem(df_cotas, 99, "Valor Total")
        valor_mezanino = obter_valor_ordem(df_cotas, 98, "Valor Total")

        return [
            i("Data-Base",                               carteira.data),
            i("Direitos Creditórios a Vencer",           carteira.a_vencer),
            i("Direitos Creditórios Vencidos",           carteira.vencido),
            i("PDD - Prov. de Perdas",                   carteira.pdd),
            i("Saldo em Tesouraria",                     carteira.saldo_tesouraria),
            i("FI BRL2314 - FI RF BRL SOB REF DI LP",    carteira.valor_di),
            i("Taxa de Administração",                   carteira.valor_administracao),
            i("Taxa Consultoria",                        carteira.recuperar_contas("Consultoria", carteira.df_contas_filtrado)),
            i("Taxa de Custódia",                        carteira.valor_taxa_custodia),
            i("Taxa de Gestão",                          carteira.valor_taxa_gestao),
            i("Taxa de Auditoria",                       carteira.valor_taxa_auditoria),
            i("Taxa ANBIMA",                             carteira.recuperar_contas("Anbima", carteira.df_contas_filtrado)),
            i("Taxa Fisc. CVM",                          0),
            i("Taxa de Performance",                     0),
            i("Outras despesas  (-)",                    carteira.outros_valores_pagar),
            i("Dif. de despesa CVM ",                    carteira.valor_taxa_cvm),
            i("Dif. de despesa ANBIMA",                  carteira.recuperar_contas("Anbima", carteira.df_contas_receber_filtrado)),
            i("Outros valores a receber  (+)",           carteira.outros_valores_receber),
            i("Ajuste de Compensação de Cotas",          0),
            i("Senior (-)",                              valor_senior * -1),
            i("Mezanino (-)",                            valor_mezanino * -1),
            i("Títulos Públicos",                        0),
            i("PL Carteira Subordinada Digitar",         carteira.patrimonio_total),
            i("Subordinação Mínima",                     0.1),
        ]

    def construir_mapeamento_mec(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        from carteira_apex import obter_valor_ordem
        df_cotas = carteira.df_cotas_superiores

        cota_sub = self._parsear_cota(carteira.recuperar_valor_carteira("Valor da Cota Líquida", 1))
        qtd_sub = carteira.recuperar_valor_carteira("Qtde. Cota", 1)

        return [
            i("DATA",                                 carteira.data),
            i("VALOR DE APLICAÇÃO SUBORDINADA",       0),
            i("COTAS EMITIDAS SUBORDINADA",           0),
            i("VALOR DE RESGATE SUBORDINADA",         0),
            i("QUANT COTAS SUBORDINADA",              qtd_sub),
            i("VALOR DA COTA SUBORDINADA",            cota_sub),
            i("AMORTIZ. DIA SUBORDINADA",             0),
            i("VALOR DE APLICAÇÃO SENIOR",            0),
            i("COTAS EMITIDAS SENIOR",                0),
            i("VALOR DE RESGATE SENIOR",              0),
            i("COTAS RESGATADAS SENIOR",              0),
            i("QUANT COTAS SENIOR",                   obter_valor_ordem(df_cotas, 99, "Qtde. Total")),
            i("VALOR DA COTA - SENIOR",               obter_valor_ordem(df_cotas, 99, "Valor Cota")),
            i("AMORTIZ. DIA SENIOR",                  0),
            i("VALOR DE APLICAÇÃO MEZANINO",          0),
            i("COTAS EMITIDAS MEZANINO",              0),
            i("VALOR DE RESGATE MEZANINO",            0),
            i("COTAS RESGATADAS MEZANINO",            0),
            i("QUANT COTAS MEZANINO",                 obter_valor_ordem(df_cotas, 98, "Qtde. Total")),
            i("VALOR DA COTA - MEZANINO",             obter_valor_ordem(df_cotas, 98, "Valor Cota")),
            i("AMORTIZ. DIA MEZANINO",                0),
        ]


# ---------------------------------------------------------------------------
# Builder: CRÉDITOS COLATERALIZADOS I
# ---------------------------------------------------------------------------


class CreditosColateralizadosReportBuilder(ReportBuilderBase):
    """Constrói os mapeamentos de relatório para CRÉDITOS COLATERALIZADOS I."""

    def construir_mapeamento_cd(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item

        return [
            i("Data-Base",                               carteira.data),
            i("Direitos Creditórios a Vencer",           0),
            i("Direitos Creditórios Vencidos",           0),
            i("PDD - Prov. de Perdas",                   carteira.pdd),
            i("BRL FIRF DI LP",                          carteira.valor_di),
            i("Taxa de Gestão",                          carteira.valor_taxa_gestao),
            i("Taxa de Auditoria",                       carteira.valor_taxa_auditoria),
            i("Taxa ANBIMA",                             carteira.recuperar_contas("Anbima", carteira.df_contas_filtrado)),
            i("Outras despesas  (-)",                    carteira.recuperar_contas("Contas a pagar", carteira.df_contas_filtrado)),
            i("Saldo em Tesouraria",                     carteira.saldo_tesouraria),
            i("Taxa de Administração",                   carteira.valor_administracao),
            i("Taxa de Custódia",                        0),
            i("Taxa de Performance",                     0),
            i("Taxa Fisc. CVM",                          carteira.valor_taxa_cvm),
            i("Dif. Despesa Anbima",                     carteira.recuperar_contas("Anbima", carteira.df_contas_receber_filtrado)),
            i("Dif. Despesa CVM",                        carteira.recuperar_contas("Cvm", carteira.df_contas_receber_filtrado)),
            i("Outros valores a receber  (+)",           carteira.recuperar_contas("Contas a receber", carteira.df_contas_receber_filtrado)),
            i("Senior (-)",                              0),
            i("Mezanino (-)",                            0),
            i("PL Carteira Subordinada Digitar",         carteira.patrimonio_total),
            i("Títulos Públicos",                        0),
        ]

    def construir_mapeamento_mec(self, carteira: CarteiraBRL) -> MapeamentoExcel:
        i = self._item
        cota_sub = self._parsear_cota(carteira.recuperar_valor_carteira("Valor da Cota Líquida", 1))
        qtd_sub = carteira.recuperar_valor_carteira("Qtde. Cota", 1)

        return [
            i("DATA",                                 carteira.data),
            i("VALOR DE APLICAÇÃO SUBORDINADA",       0),
            i("COTAS EMITIDAS SUBORDINADA",           0),
            i("VALOR DE RESGATE  SUBORDINADA",        0),
            i("VALOR DE RESGATE SUBORDINADA",         0),
            i("QUANT COTAS SUBORDINADA",              qtd_sub),
            i("VALOR DA COTA SUBORDINADA",            cota_sub),
            i("AMORTIZ. DIA SUBORDINADA",             0),
            i("VALOR DE APLICAÇÃO MEZANINO",          0),
            i("COTAS EMITIDAS MEZANINO",              0),
            i("VALOR DE RESGATE MEZANINO",            0),
            i("COTAS RESGATADAS MEZANINO",            0),
            i("QUANT COTAS MEZANINO",                 0),
            i("VALOR DA COTA - MEZANINO",             0),
            i("AMORTIZ. DIA MEZANINO",                0),
            i("VALOR DE APLICAÇÃO SENIOR",            0),
            i("COTAS EMITIDAS SENIOR",                0),
            i("VALOR DE RESGATE SENIOR",              0),
            i("COTAS RESGATADAS SENIOR",              0),
            i("QUANT COTAS SENIOR",                   0),
            i("VALOR DA COTA - SENIOR",               0),
            i("AMORTIZ. DIA SENIOR",                  0),
        ]


# ---------------------------------------------------------------------------
# Builder: AVANTI FIDC
# ---------------------------------------------------------------------------


class AvantiReportBuilder(ReportBuilderBase):
    """Constrói os mapeamentos de relatório para o AVANTI FIDC.

    Administradora: Avanti (CarteiraAVANTI)
    """

    def construir_mapeamento_cd(self, carteira: CarteiraBase) -> MapeamentoExcel:
        i = self._item
        import pandas as pd
        import numpy as np

        def somar_valores_intervalo(inicio, fim, df, coluna, codigo):
            def to_float_strict(v):
                if hasattr(v, "iloc"):
                    v = v.iloc[0]
                if v is None:
                    return 0.0
                if isinstance(v, float) and np.isnan(v):
                    return 0.0
                try:
                    val = float(v)
                    if np.isnan(val):
                        return 0.0
                    return val
                except:
                    return 0.0

            total = 0.0
            for row in range(inicio, fim):
                try:
                    valor = df[df[coluna] == codigo].values[0, row]
                    total += to_float_strict(valor)
                except:
                    pass
            return total

        df = carteira.dataframe

        id_rf = somar_valores_intervalo(80, 95, df, "Unnamed: 1", "ID RF LP FIC FI")
        santander = somar_valores_intervalo(80, 95, df, "Unnamed: 1", "SAN RF REF DI TITULOS PUB PREMIUM FC FI ")
        firf_id = somar_valores_intervalo(95, 105, df, "Unnamed: 1", "FIRF ID SOBERANO")
        carmel = somar_valores_intervalo(90, 105, df, "Unnamed: 1", "FIDC CARMEL II")
        ctr_itambe = somar_valores_intervalo(95, 105, df, "Unnamed: 1", 29690)
        saldo_tesouraria = somar_valores_intervalo(70, 90, df, "Unnamed: 2", "Total Saldos em Conta Corrente:")
        patrimonio_total = somar_valores_intervalo(70, 80, df, "Unnamed: 1", "PATRIMÔNIO FECHAMENTO")

        a_receber = 0
        try:
            a_receber = float(df[df["Unnamed: 1"] == "PAGAMENTO TAXA ADMINISTRAÇÃO - PAGO A MAIOR "].values[0, 81])
        except:
            pass

        def recuperar_valor_estoque(df_est, cod):
            try:
                return df_est[df_est["SEU_NUMERO"] == cod].iloc[0, 1]
            except:
                return 0

        versa_1, versa_2, versa_3, itambe_estoque = 0, 0, 0, 0
        try:
            df_estoque = pd.read_excel(carteira.path_carteira, sheet_name="ESTOQUE_ATUAL")
            df_estoque = df_estoque[["SEU_NUMERO", "VALOR_PRESENTE"]]
            versa_1 = recuperar_valor_estoque(df_estoque, 551995)
            versa_2 = recuperar_valor_estoque(df_estoque, 774293)
            versa_3 = recuperar_valor_estoque(df_estoque, 774294)
            itambe_estoque = recuperar_valor_estoque(df_estoque, "U0003360000001")
        except:
            pass

        def recup_contas(df_c, txt):
            try:
                if df_c is None or df_c.empty: return 0.0
                return df_c[df_c["Descrição"].str.contains(txt, case=False, na=False)]["Valor"].sum()
            except:
                return 0.0

        a_receber += recup_contas(carteira.df_contas_receber, "Pagamento ir - amortização")
        a_receber_adm = recup_contas(carteira.df_contas_receber, "Pagamento de Taxa Administração") + recup_contas(carteira.df_contas_receber, "Pagamento taxa de administração")
        
        a_receber_gestao = recup_contas(carteira.df_contas_receber, "Pagamento taxa gestão") * -1
        a_receber_gestao += recup_contas(carteira.df_contas_pagar, "Pagamento taxa gestão")

        data = pd.to_datetime(carteira.data, errors='coerce') if carteira.data else ""

        return [
            i("Data-Base",                                                      data),
            i("Direitos Creditórios a Vencer",                                  0),     
            i("Direitos Creditórios Vencidos",                                  0), 
            i("Direitos Creditórios - Precatórios",                             0), 
            i("NC - CTR ITAMBE - SANEAMENTO LTDA 16046547",                     itambe_estoque), 
            i("CTR ITAMBE SANEAMENTO LTDA 2202",                                ctr_itambe), 
            i("EBS EMPRESA BRASILEIRA DE SANEAMENTO LTDA 16046549",             0), 
            i("VERSA ENGENHARIA AMBIENTAL LTDA 16046548",                       versa_1), 
            i("VERSA ENGENHARIA AMBIENTAL LTDA 16046550",                       versa_2), 
            i("VERSA ENGENHARIA AMBIENTAL LTDA 16046551",                       versa_3), 
            i("CARMEL II FIDC",                                                 carmel), 
            i("PDD - Prov. de Perdas",                                          0), 
            i("Saldo em Tesouraria",                                            saldo_tesouraria), 
            i("FIRF ID Soberano",                                               firf_id), 
            i("ID RF LP FIC FI",                                                id_rf), 
            i("Santander RF Ref. DI Tít. Píblicos Premium",                     santander), 
            i("Taxa Fisc. CVM",                                                 carteira.valor_taxa_cvm),
            i("Taxa de Administração",                                          carteira.valor_administracao + a_receber_adm),
            i("Taxa de Custódia",                                               carteira.valor_taxa_custodia),
            i("Taxa de Gestão",                                                 carteira.valor_taxa_gestao + a_receber_gestao),
            i("Taxa de Auditoria",                                              carteira.valor_taxa_auditoria), 
            i("Despesa Cetip/Selic",                                            carteira.valor_cetip),
            i("Outras despesas  (-)",                                           carteira.outros_valores_pagar),  
            i("Taxa ANBIMA",                                                    carteira.valor_anbima),  
            i("Taxa de Performance",                                            0), 
            i("Diferimento de despesa  CVM ",                                   0), 
            i("Dif. de despesa ANBIMA",                                         0),
            i("Senior (-)",                                                     0), 
            i("Mezanino (-)",                                                   0), 
            i("Títulos Públicos",                                               0), 
            i("Outros valores a receber  (+)",                                  a_receber), 
            i("PL Carteira Subordinada",                                        patrimonio_total),
        ]

    def construir_mapeamento_mec(self, carteira: CarteiraBase) -> MapeamentoExcel:
        i = self._item
        import numpy as np

        def somar_valores_intervalo(inicio, fim, df, coluna, codigo):
            def to_float_strict(v):
                if hasattr(v, "iloc"):
                    v = v.iloc[0]
                if v is None:
                    return 0.0
                if isinstance(v, float) and np.isnan(v):
                    return 0.0
                try:
                    val = float(v)
                    if np.isnan(val):
                        return 0.0
                    return val
                except:
                    return 0.0

            total = 0.0
            for row in range(inicio, fim):
                try:
                    valor = df[df[coluna] == codigo].values[0, row]
                    total += to_float_strict(valor)
                except:
                    pass
            return total

        df = carteira.dataframe
        qtd_cota = somar_valores_intervalo(2, 15, df, "Unnamed: 3", "Qtd. Cotas")
        valor_cota = somar_valores_intervalo(45, 63, df, "Unnamed: 3", "Qtd. Cotas")

        import pandas as pd
        data = pd.to_datetime(carteira.data, errors='coerce') if carteira.data else ""

        return [
            i("DATA",                       data),
            i("VALOR DE APLICAÇÃO",         0),
            i("VALOR DE RESGATE ",          0),
            i("COTAS RESGATADAS",           0),
            i("COTAS EMITIDAS",             0),
            i("QUANT COTAS",                qtd_cota),
            i("VALOR DA COTA",              valor_cota),   
            i("AMORTIZ. DIA",               0),
        ]
