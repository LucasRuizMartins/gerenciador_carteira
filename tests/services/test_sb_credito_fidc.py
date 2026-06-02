"""
Testes unitários para o mapeamento SB_CREDITO_FIDC.

Verifica que:
1. O JSON é válido e carregável pelo schema Pydantic.
2. Os novos resolvers customizados (resolver_sb_valor_senior, resolver_sb_valor_mezanino, resolver_sb_senior, resolver_sb_mezanino) funcionam corretamente.
3. Todas as categorias de CD e MEC são resolvidas e batem com os valores esperados.
"""

from __future__ import annotations

import sys
import os
from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from src.services.config_driven_builder import ConfigDrivenBuilder
from src.services.mapping_engine import MappingEngine


# ===========================================================================
# Fixture — Carteira mock tipo CarteiraSingulareQI
# ===========================================================================

@pytest.fixture
def carteira_sb():
    """Mock de carteira com estrutura da CarteiraSingulareQI para SB CREDITO FIDC."""
    m = MagicMock()

    # Data e patrimônio
    m.data = date(2025, 6, 2)
    m.patrimonio_total = 80_000_000.0
    m.saldo_tesouraria = 3_400_000.0
    m.pdd = -1_200_000.0

    # Taxas
    m.valor_administracao = -25_000.0
    m.valor_taxa_gestao = -40_000.0
    m.valor_taxa_custodia = -8_000.0
    m.valor_taxa_auditoria = -4_500.0
    m.valor_taxa_cvm = -2_000.0
    m.valor_selic = -1_200.0
    m.valor_cetip = -900.0
    m.valor_liq_banco = -1_500.0
    m.valor_anbima = -500.0
    m.valor_taxa_performance = 0.0

    # _dataframes: simulando as seções da planilha Singulare
    m._dataframes = {
        "nc": pd.DataFrame({"Valor Líquido": [15_000_000.0, 10_000_000.0]}),  # NCPX a vencer = 25M
        "vcnc": pd.DataFrame({"Valor Líquido": [2_500_000.0]}),                # CCB/NC vencidos = 2.5M
        "pddnc": pd.DataFrame({"Valor Líquido": [-800_000.0]}),                # PDD CCB = -800K
        "pdd_l": pd.DataFrame({"Valor Líquido": [-300_000.0]}),                # PDD Líquido = -300K
        "ltno": pd.DataFrame({"Valor Líquido": [4_000_000.0]}),                # ltno = 4M
        "ntn o": pd.DataFrame({"Valor Líquido": [2_000_000.0]}),               # ntn o = 2M
        "ntn": pd.DataFrame({"Valor Líquido": [6_000_000.0]}),                 # ntn = 6M
        "vdprz": pd.DataFrame({"Valor Líquido": [500_000.0]}),                 # vdprz = 500K
        "senior": pd.DataFrame({
            "CATEGORIA": ["SENIOR 5", "SENIOR 6", "SENIOR 7", "SENIOR 8", "SENIOR 10", "SENIOR 11", "SENIOR 12", "SENIOR 13"],
            "Valor Bruto": [5_000_000.0] * 8, # 40M total
            "PU Mercado": [1000.5, 1000.6, 1000.7, 1000.8, 1001.0, 1001.1, 1001.2, 1001.3],
        }),
        "mezanino": pd.DataFrame({
            "CATEGORIA": ["MEZANINO E", "MEZANINO F", "MEZANINO G", "MEZANINO H", "MEZANINO I", "MEZANINO J", "MEZANINO K", "MEZANINO L", "MEZANINO M", "MEZANINO N"],
            "Valor Bruto": [2_000_000.0] * 10, # 20M total
            "PU Mercado": [500.5, 500.6, 500.7, 500.8, 500.9, 501.0, 501.1, 501.2, 501.3, 501.4],
        }),
    }

    # df_senior e df_mezanino via atributos diretos
    m.df_senior = m._dataframes["senior"]
    m.df_mezanino = m._dataframes["mezanino"]

    # df_contas_filtrado (resultado de _agrupar_contas com CATEGORIA/Valor)
    m.df_contas_filtrado = pd.DataFrame({
        "CATEGORIA": ["Administração", "Gestão", "Auditoria", "Custódia", "CVM",
                      "consultoria", "cetip", "selic", "Banco Liquidante",
                      "Contas a pagar", "Contas a receber", "Compensação",
                      "Contingencia Judicial", "Resgate de Cotas", "liquidação"],
        "Valor": [-25_000.0, -40_000.0, -4_500.0, -8_000.0, -2_000.0,
                  -2_000.0, -900.0, -1_200.0, -1_500.0,
                  -5_000.0, 1_200.0, -3_000.0,
                  -50_000.0, -20_000.0, -450.0],
    })

    # recuperar_valor_carteira
    def mock_recuperar(chave, coluna):
        if chave == "Qtd Cota" and coluna == 1:
            return 1_250_000.0
        if chave == "Vlr Cota" and coluna == 1:
            return 15.67
        if chave == "SBCRAV" and coluna == "Valor Líquido":
            return 12_000_000.0
        if chave == "SBCRVE" and coluna == "Valor Líquido":
            return 1_500_000.0
        if chave == "739704" and coluna == "Valor Líquido":
            return 500_000.0
        if chave == "PDD" and (coluna == 11 or coluna == "Valor Total"):
            return -1_200_000.0
        if chave == "GLEBA04" and (coluna == 11 or coluna == "Valor Total"):
            return 100_000.0
        if chave == "MT102245" and (coluna == 11 or coluna == "Valor Total"):
            return 150_000.0
        if chave == "MT 26485" and (coluna == 11 or coluna == "Valor Total"):
            return 80_000.0
        if chave == "MAQSESMI" and (coluna == 11 or coluna == "Valor Total"):
            return 220_000.0
        if chave == "FAZ.EST.VIRGINIA" and (coluna == 11 or coluna == "Valor Total" or coluna == "Descrição"):
            return 400_000.0
        return 0.0
    m.recuperar_valor_carteira.side_effect = mock_recuperar

    # recuperar_contas — busca no df_contas_filtrado
    def mock_recuperar_contas(filtro, df, coluna_filtro="CATEGORIA"):
        if df is None or df.empty:
            return 0.0
        try:
            col_desc = df.columns[0]
            col_val = df.columns[1]
            mask = df[col_desc].astype(str).str.contains(filtro, case=False, na=False)
            resultado = df.loc[mask, col_val]
            return float(resultado.sum()) if not resultado.empty else 0.0
        except Exception:
            return 0.0
    m.recuperar_contas.side_effect = mock_recuperar_contas

    return m


# ===========================================================================
# Testes do JSON e Mapeamentos
# ===========================================================================

class TestSbCreditoJson:
    """Valida a estrutura do JSON de mapeamento do SB CREDITO FIDC."""

    def test_carregavel_e_schema(self):
        builder = ConfigDrivenBuilder.de_arquivo("SB_CREDITO_FIDC.json")
        assert builder.fundo == "SB_CREDITO_FIDC"
        assert builder.administradora == "SINGULARE"

    def test_cd_completo(self, carteira_sb):
        builder = ConfigDrivenBuilder.de_arquivo("SB_CREDITO_FIDC.json")
        resultado = builder.construir_mapeamento_cd(carteira_sb)
        
        # Data
        dt = next(r["Valor"] for r in resultado if r["Categoria"] == "Data-Base")
        assert dt == date(2025, 6, 2)

        # Saldo em Tesouraria
        tes = next(r["Valor"] for r in resultado if r["Categoria"] == "Saldo em Tesouraria")
        assert tes == 3_400_000.0

        # Direitos Creditórios a Vencer
        av = next(r["Valor"] for r in resultado if r["Categoria"] == "Direitos Creditórios a Vencer")
        assert av == 12_000_000.0

        # Títulos Privados [CCB/NC a vencer]
        ccb_v = next(r["Valor"] for r in resultado if r["Categoria"] == "Títulos Privados [CCB/NC a vencer]")
        assert ccb_v == 25_000_000.0

        # Títulos Privados [CCB/NC - vencidos]
        ccb_venc = next(r["Valor"] for r in resultado if r["Categoria"] == "Títulos Privados [CCB/NC - vencidos]")
        assert ccb_venc == 2_500_000.0

        # Over/Compromissada (ltno=4M + ntn o=2M = 6M)
        over = next(r["Valor"] for r in resultado if r["Categoria"] == "Over/Compromissada")
        assert over == 6_000_000.0

        # PDD - Prov. de Perdas (Duplicatas) (PDD=-1.2M + pdd_l=-300K = -1.5M)
        pdd = next(r["Valor"] for r in resultado if r["Categoria"] == "PDD - Prov. de Perdas (Duplicatas)")
        assert pdd == -1_500_000.0

        # PDD - Prov. de Perdas (CCB) (pddnc=-800K)
        pdd_ccb = next(r["Valor"] for r in resultado if r["Categoria"] == "PDD - Prov. de Perdas (CCB)")
        assert pdd_ccb == -800_000.0

        # Garantia/Execução (GLEBA04=100K + MT102245=150K + MT 26485=80K + MAQSESMI=220K + vdprz=500K + FAZ.EST.VIRGINIA=400K = 1.45M)
        gar = next(r["Valor"] for r in resultado if r["Categoria"] == "Garantia/Execução")
        assert gar == 1_450_000.0

        # Senior (-) (resolver_sb_valor_senior = 40M)
        senior = next(r["Valor"] for r in resultado if r["Categoria"] == "Senior (-)")
        assert senior == 40_000_000.0

        # Mezanino (-) (resolver_sb_valor_mezanino = 20M)
        mezan = next(r["Valor"] for r in resultado if r["Categoria"] == "Mezanino (-)")
        assert mezan == 20_000_000.0

        # PL da Carteira (patrimonio_total = 80M)
        pl = next(r["Valor"] for r in resultado if r["Categoria"] == "PL da Carteira")
        assert pl == 80_000_000.0

    def test_mec_completo(self, carteira_sb):
        builder = ConfigDrivenBuilder.de_arquivo("SB_CREDITO_FIDC.json")
        resultado = builder.construir_mapeamento_mec(carteira_sb)
        
        # QUANT COTAS
        qtd = next(r["Valor"] for r in resultado if r["Categoria"] == "QUANT COTAS")
        assert qtd == 1_250_000.0

        # VALOR COTA SUBORDINADA
        cota_sub = next(r["Valor"] for r in resultado if r["Categoria"] == "VALOR COTA SUBORDINADA")
        assert cota_sub == 15.67

        # MEZANINO E cota (500.5)
        mez_e = next(r["Valor"] for r in resultado if r["Categoria"] == "MEZANINO E")
        assert mez_e == 500.5

        # MEZANINO N cota (501.4)
        mez_n = next(r["Valor"] for r in resultado if r["Categoria"] == "MEZANINO N")
        assert mez_n == 501.4

        # SENIOR 5 cota (1000.5)
        sen_5 = next(r["Valor"] for r in resultado if r["Categoria"] == "SENIOR 5")
        assert sen_5 == 1000.5

        # SENIOR 13 cota (1001.3)
        sen_13 = next(r["Valor"] for r in resultado if r["Categoria"] == "SENIOR 13")
        assert sen_13 == 1001.3

        # % SUBORDINAÇÃO SENIOR (0.32)
        sub_sen = next(r["Valor"] for r in resultado if r["Categoria"] == "% SUBORDINAÇÃO SENIOR")
        assert sub_sen == 0.32


class TestCarteiraSingulareQILookup:
    """Valida a funcionalidade de recuperação de valor em sub-dataframes da CarteiraSingulareQI."""

    def test_recuperar_valor_carteira_sub_dataframes(self):
        from Carteira import CarteiraSingulareQI
        
        carteira = CarteiraSingulareQI()
        
        # Cria dataframes de teste para simular as seções fatiadas
        df_oa = pd.DataFrame({
            "Código": ["GLEBA04", "MT102245"],
            "Descrição": ["Gleba 4 Desc", "MT Desc"],
            "Valor Total": [100_000.0, 150_000.0]
        })
        
        df_of = pd.DataFrame({
            "Ativo": ["SBCRAV", "739704"],
            "Valor Líquido": [12_000_000.0, 500_000.0]
        })
        
        carteira._dataframes = {
            "outros_ativos": df_oa,
            "outros_fundos": df_of
        }
        
        # 1. Busca por string exata (coluna e código)
        assert carteira.recuperar_valor_carteira("GLEBA04", "Valor Total") == 100_000.0
        assert carteira.recuperar_valor_carteira("SBCRAV", "Valor Líquido") == 12_000_000.0
        
        # 2. Busca por índice de coluna (inteiro)
        assert carteira.recuperar_valor_carteira("MT102245", 2) == 150_000.0
        assert carteira.recuperar_valor_carteira("739704", 1) == 500_000.0
        
        # 3. Busca por código com espaço / minúsculo (case-insensitive)
        assert carteira.recuperar_valor_carteira("gleba04", "Valor Total") == 100_000.0
        assert carteira.recuperar_valor_carteira(" sbcrav ", "Valor Líquido") == 12_000_000.0
        
        # 4. Caso de código inexistente
        assert carteira.recuperar_valor_carteira("INEXISTENTE", "Valor Total") == 0.0

