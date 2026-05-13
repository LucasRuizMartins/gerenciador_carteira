"""
Fixtures compartilhadas para todos os testes do sistema de carteiras.

Este arquivo é carregado automaticamente pelo pytest antes de qualquer teste.
Fixtures aqui definidas ficam disponíveis para todos os módulos de teste
sem necessidade de import explícito.
"""

from __future__ import annotations

import pytest
import pandas as pd


# ---------------------------------------------------------------------------
# Fixtures: DataFrames sintéticos (sem dependência de arquivos Excel reais)
# ---------------------------------------------------------------------------


@pytest.fixture
def df_contas_pagar_basico() -> pd.DataFrame:
    """DataFrame mínimo simulando um bloco de contas a pagar.

    Contém categorias conhecidas (gestão, anbima) e uma não-mapeada
    (fornecedor) para testar a classificação automática como 'Contas a pagar'.
    """
    return pd.DataFrame({
        "Histórico": [
            "Taxa de Gestão",
            "Taxa ANBIMA",
            "Pagamento fornecedor",
            "Taxa de Auditoria",
        ],
        "Valor Total": [-1_500.0, -250.0, -300.0, -800.0],
    })


@pytest.fixture
def df_contas_misto() -> pd.DataFrame:
    """DataFrame com contas a pagar (negativo) e a receber (positivo).

    Usado para verificar a classificação bidirecional de ``classificar_contas``.
    """
    return pd.DataFrame({
        "Histórico": [
            "Taxa de Gestão",
            "Dif ANBIMA a receber",
            "Crédito diverso",
            "Taxa CVM",
        ],
        "Valor Total": [-2_000.0, 500.0, 1_200.0, -150.0],
    })


@pytest.fixture
def df_planilha_com_marcadores() -> pd.DataFrame:
    """DataFrame simulando a estrutura de uma planilha BRL com marcadores."""
    dados = [
        ["Data Posição", "31/12/2024", None],
        ["A VENCER", None, 1_000_000.0],
        ["VENCIDO", None, 50_000.0],
        ["VALORES A LIQUIDAR", None, None],
        ["Gestão", None, -1_500.0],
        ["ANBIMA", None, -250.0],
        ["SALDOS EM CONTA CORRENTE", None, None],
        ["Conta corrente BRL", None, 35_000.0],
        ["RESUMO DA CARTEIRA", None, None],
        ["PL Posição", 2_500_000.0, None],
    ]
    return pd.DataFrame(dados, columns=["Carteira", "Unnamed: 1", "Unnamed: 2"])


@pytest.fixture
def palavras_chave_padrao() -> list[str]:
    """Lista padrão de palavras-chave usadas na maioria dos fundos."""
    return [
        "Administração", "ANBIMA", "Auditoria",
        "Custódia", "CVM", "Gestão",
        "SELIC", "CETIP", "Banco Liquidante",
    ]


# ---------------------------------------------------------------------------
# Fixtures: Objetos carteira com mock de dados
# ---------------------------------------------------------------------------


@pytest.fixture
def carteira_base_concreta():
    """Instância de uma implementação mínima de CarteiraBase para teste.

    Retorna uma subclasse concreta que implementa os métodos abstratos
    com comportamento vazio (não carrega arquivos Excel).
    """
    import sys
    import os
    # Garante que o diretório raiz está no path para importar Carteira.py
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if raiz not in sys.path:
        sys.path.insert(0, raiz)

    from Carteira import CarteiraBase

    class CarteiraConcretaVazia(CarteiraBase):
        """Implementação mínima para testar CarteiraBase em isolamento."""

        def carregar_dados(self, aba: str = "CD_ATUAL") -> None:
            """Não carrega dados — usada apenas em testes unitários."""
            pass

        def _processar_planilha(self, aba: str = "CD_ATUAL") -> dict:
            """Retorna dicionário vazio."""
            return {}

    return CarteiraConcretaVazia()
