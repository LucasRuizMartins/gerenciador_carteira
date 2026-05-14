"""
Testes de regressão para a Sprint 1.2 — Migração piloto.

Objetivo: garantir que o ConfigDrivenBuilder (lendo JSON) produz
exatamente o mesmo resultado que o builder legado hardcoded.

Estratégia:
    - Usa um CarteiraMock completo com os mesmos valores
    - Compara categoria a categoria entre os dois builders
    - Detecta qualquer divergência na estrutura ou nos valores

Fundos testados:
    - ZULU FIP (ZuluReportBuilder → mapeamentos/ZULU.json)
    - CRÉDITOS COLATERALIZADOS I (CreditosColateralizadosReportBuilder → mapeamentos/CREDITOS_COLATERALIZADOS.json)
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

from src.services.report_builder import ZuluReportBuilder, CreditosColateralizadosReportBuilder
from src.services.config_driven_builder import ConfigDrivenBuilder


# ===========================================================================
# Fixture — Carteira mock completa
# ===========================================================================

@pytest.fixture
def carteira():
    """Mock de carteira com todos os atributos usados pelos builders ZULU e CC."""
    m = MagicMock()

    # Atributos básicos
    m.data = date(2024, 12, 31)
    m.patrimonio_total = 1_500_000.0
    m.saldo_tesouraria = 50_000.0
    m.a_vencer = 800_000.0
    m.vencido = 100_000.0
    m.pdd = -30_000.0
    m.valor_di = 20_000.0

    # Taxas
    m.valor_administracao = -1_000.0
    m.valor_taxa_gestao = -2_000.0
    m.valor_taxa_cvm = -500.0
    m.valor_taxa_auditoria = -300.0
    m.valor_taxa_custodia = -200.0

    # DataFrames de contas
    m.df_contas_filtrado = pd.DataFrame({
        "Histórico": ["Anbima", "Contas a pagar", "Cvm"],
        "Valor Total": [-100.0, -500.0, -50.0],
    })
    m.df_contas_receber_filtrado = pd.DataFrame({
        "Histórico": ["Anbima", "Cvm", "Contas a receber"],
        "Valor Total": [80.0, 40.0, 200.0],
    })

    # recuperar_valor_carteira
    def mock_recuperar(chave, coluna):
        valores = {
            ("GRUPO MPR PARTICIP", 8): 999_000.0,
            ("Qtde. Cota", 1): 500_000.0,
            ("Valor da Cota Líquida", 1): "1,234567",
        }
        return valores.get((chave, coluna), 0.0)
    m.recuperar_valor_carteira.side_effect = mock_recuperar

    # recuperar_contas
    def mock_recuperar_contas(filtro, df):
        if df is None or df.empty:
            return 0.0
        col_desc = df.columns[0]
        col_val = df.columns[1]
        mask = df[col_desc].str.contains(filtro, case=False, na=False)
        resultado = df.loc[mask, col_val]
        return float(resultado.values[0]) if not resultado.empty else 0.0
    m.recuperar_contas.side_effect = mock_recuperar_contas

    return m


# ===========================================================================
# Helpers
# ===========================================================================

def comparar_mapeamentos(legado: list[dict], novo: list[dict], nome: str) -> None:
    """Compara dois mapeamentos categoria a categoria e falha com mensagem clara."""
    assert len(legado) == len(novo), (
        f"{nome}: número de itens diferente — legado={len(legado)}, novo={len(novo)}\n"
        f"Legado: {[i['Categoria'] for i in legado]}\n"
        f"Novo:   {[i['Categoria'] for i in novo]}"
    )
    for idx, (item_l, item_n) in enumerate(zip(legado, novo)):
        assert item_l["Categoria"] == item_n["Categoria"], (
            f"{nome}[{idx}]: categoria diferente\n"
            f"  Legado: {item_l['Categoria']!r}\n"
            f"  Novo:   {item_n['Categoria']!r}"
        )
        val_l = item_l["Valor"]
        val_n = item_n["Valor"]

        # Para valores numéricos, tolera diferença de ponto flutuante
        if isinstance(val_l, (int, float)) and isinstance(val_n, (int, float)):
            assert abs(float(val_l) - float(val_n)) < 1e-6, (
                f"{nome}[{idx}] '{item_l['Categoria']}': valor diferente\n"
                f"  Legado: {val_l}\n"
                f"  Novo:   {val_n}"
            )
        else:
            assert val_l == val_n, (
                f"{nome}[{idx}] '{item_l['Categoria']}': valor diferente\n"
                f"  Legado: {val_l!r}\n"
                f"  Novo:   {val_n!r}"
            )


# ===========================================================================
# Testes de regressão ZULU
# ===========================================================================

class TestRegressaoZulu:
    """Garante que ZULU.json produz o mesmo resultado que ZuluReportBuilder."""

    def test_cd_identico_ao_legado(self, carteira):
        legado = ZuluReportBuilder().construir_mapeamento_cd(carteira)
        novo = ConfigDrivenBuilder.de_arquivo("ZULU.json").construir_mapeamento_cd(carteira)
        comparar_mapeamentos(legado, novo, "ZULU/CD")

    def test_mec_identico_ao_legado(self, carteira):
        legado = ZuluReportBuilder().construir_mapeamento_mec(carteira)
        novo = ConfigDrivenBuilder.de_arquivo("ZULU.json").construir_mapeamento_mec(carteira)
        comparar_mapeamentos(legado, novo, "ZULU/MEC")

    def test_json_valido_e_carregavel(self):
        """O JSON deve ser parseável pelo schema Pydantic sem erros."""
        builder = ConfigDrivenBuilder.de_arquivo("ZULU.json")
        assert builder.fundo == "ZULU"
        assert builder.administradora == "BRL"
        assert len(builder._config.mapeamento_cd) > 0
        assert len(builder._config.mapeamento_mec) > 0


# ===========================================================================
# Testes de regressão CREDITOS_COLATERALIZADOS
# ===========================================================================

class TestRegressaoCreditosColateralizados:
    """Garante que CREDITOS_COLATERALIZADOS.json produz o mesmo resultado que o builder legado."""

    def test_cd_identico_ao_legado(self, carteira):
        legado = CreditosColateralizadosReportBuilder().construir_mapeamento_cd(carteira)
        novo = ConfigDrivenBuilder.de_arquivo("CREDITOS_COLATERALIZADOS.json").construir_mapeamento_cd(carteira)
        comparar_mapeamentos(legado, novo, "CREDITOS_COLATERALIZADOS/CD")

    def test_mec_identico_ao_legado(self, carteira):
        legado = CreditosColateralizadosReportBuilder().construir_mapeamento_mec(carteira)
        novo = ConfigDrivenBuilder.de_arquivo("CREDITOS_COLATERALIZADOS.json").construir_mapeamento_mec(carteira)
        comparar_mapeamentos(legado, novo, "CREDITOS_COLATERALIZADOS/MEC")

    def test_json_valido_e_carregavel(self):
        builder = ConfigDrivenBuilder.de_arquivo("CREDITOS_COLATERALIZADOS.json")
        assert builder.fundo == "CREDITOS_COLATERALIZADOS"
        assert builder.administradora == "BRL"
        assert len(builder._config.mapeamento_cd) > 0
        assert len(builder._config.mapeamento_mec) > 0
