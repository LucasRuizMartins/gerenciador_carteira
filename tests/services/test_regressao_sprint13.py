"""
Testes de regressão para a Sprint 1.3 — Migração em Massa.

Garante paridade total entre builders legados e ConfigDrivenBuilder para:
FIDARA, CDC, CARMEL_II, GERAR, ENEL, HOUSI, INFRA, MOOVPAY, RESIDENCE, VIRTUS.
"""

from __future__ import annotations
import sys
import os
from datetime import date
from unittest.mock import MagicMock
import pandas as pd
import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RAIZ not in sys.path: sys.path.insert(0, _RAIZ)

from src.services.report_builder import (
    FidaraReportBuilder, CdcReportBuilder, CarmelIIReportBuilder,
    GerarReportBuilder, EnelReportBuilder, HousiReportBuilder,
    InfraReportBuilder, MoovpayReportBuilder, ResidenceReportBuilder,
    VirtusReportBuilder, SbIIReportBuilder, AvantiReportBuilder
)
from src.services.config_driven_builder import ConfigDrivenBuilder

@pytest.fixture
def carteira():
    m = MagicMock()
    m.data = date(2024, 12, 31)
    m.patrimonio_total = 1000000.0
    m.saldo_tesouraria = 50000.0
    m.a_vencer = 800000.0
    m.vencido = 100000.0
    m.pdd = -30000.0
    m.valor_di = 20000.0
    m.valor_administracao = -1000.0
    m.valor_taxa_gestao = -2000.0
    m.valor_taxa_cvm = -500.0
    m.valor_taxa_auditoria = -300.0
    m.valor_taxa_custodia = -200.0
    m.valor_anbima = -150.0
    m.valor_taxa_performance = 0.0
    m.outros_valores_receber = 5000.0
    m.outros_valores_pagar = -1500.0
    
    m.df_contas_filtrado = pd.DataFrame({"Histórico": ["Cvm", "Anbima", "Contas a pagar"], "Valor Total": [-50, -100, -500]})
    m.df_contas_receber_filtrado = pd.DataFrame({"Histórico": ["Anbima", "Cvm", "Contas a receber"], "Valor Total": [80, 40, 200]})
    m.df_contas_receber = m.df_contas_receber_filtrado # Para Moovpay
    
    m.df_cotas_superiores = pd.DataFrame({
        "Ordem": [99, 98, 97, 96, 95, 94, 93],
        "Valor Total": [10000, 20000, 5000, 4000, 3000, 15000, 2000],
        "Qtde. Total": [100, 200, 50, 40, 30, 150, 20],
        "Valor Cota": [100, 100, 100, 100, 100, 100, 100]
    })

    def mock_recuperar(chave, coluna):
        if chave == "PERDA ESPERADA": return -5000.0
        if chave == "Valor da Cota Líquida": return "1,50"
        if chave == "Qtde. Cota": return 100000.0
        return 0.0
    m.recuperar_valor_carteira.side_effect = mock_recuperar

    def mock_contas(filtro, df):
        # Simula a busca de valores nas tabelas de contas
        valores = {"Cvm": -50.0, "Anbima": -100.0, "Contas a pagar": -500.0, 
                   "Contas a receber": 200.0, "Consultoria": -150.0, "Custódia": -200.0,
                   "Taxa de consultoria": -300.0, "Cetip": -20.0, "Selic": -10.0,
                   "Banco Liquidante": -123.45, "Gestão": 500.0, "Performance": -1000.0}
        return valores.get(filtro, 0.0)
    m.recuperar_contas.side_effect = mock_contas
    
    m.dataframe = pd.DataFrame({"Carteira": ["FICFI ITAU SOBERANO RF SIMP LP"], "Unnamed: 2": ["banco liquidante"], "Unnamed: 4": [123.45], 5: [50000.0]})
    
    return m

def comparar(legado, novo, nome):
    assert len(legado) == len(novo), f"{nome}: tamanho diferente"
    for idx, (l, n) in enumerate(zip(legado, novo)):
        assert l["Categoria"] == n["Categoria"], f"{nome}[{idx}] categoria"
        val_l, val_n = l["Valor"], n["Valor"]
        # Normalização de tipos para comparação (ex: Timestamp vs date)
        if all(hasattr(val_l, attr) for attr in ["year", "month", "day"]):
            val_l = date(val_l.year, val_l.month, val_l.day)
        if all(hasattr(val_n, attr) for attr in ["year", "month", "day"]):
            val_n = date(val_n.year, val_n.month, val_n.day)

        if isinstance(val_l, (int, float)):
            assert abs(float(val_l) - float(val_n)) < 1e-6, f"{nome}[{idx}] valor {l['Categoria']}: {val_l} != {val_n}"
        else:
            assert val_l == val_n

@pytest.mark.parametrize("builder_class, json_file", [
    (FidaraReportBuilder, "FIDARA.json"),
    (CdcReportBuilder, "CDC.json"),
    (CarmelIIReportBuilder, "CARMEL_II.json"),
    (GerarReportBuilder, "GERAR.json"),
    (EnelReportBuilder, "ENEL.json"),
    (HousiReportBuilder, "HOUSI.json"),
    (InfraReportBuilder, "INFRA.json"),
    (MoovpayReportBuilder, "MOOVPAY.json"),
    (ResidenceReportBuilder, "RESIDENCE.json"),
    (VirtusReportBuilder, "VIRTUS.json"),
    (SbIIReportBuilder, "SB_II.json"),
    (AvantiReportBuilder, "AVANTI.json"),
])
def test_regressao_sprint13(carteira, builder_class, json_file):
    builder_legado = builder_class()
    builder_novo = ConfigDrivenBuilder.de_arquivo(json_file)
    
    comparar(builder_legado.construir_mapeamento_cd(carteira), builder_novo.construir_mapeamento_cd(carteira), f"{json_file}/CD")
    comparar(builder_legado.construir_mapeamento_mec(carteira), builder_novo.construir_mapeamento_mec(carteira), f"{json_file}/MEC")
