from __future__ import annotations
from _pytest import cacheprovider
# pyrefly: ignore [invalid-syntax]

import sys
import os
import pytest
import pandas as pd
from datetime import date

# Garante que o diretório raiz do projeto está no sys.path
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from src.services.report_builder import FidaraReportBuilder, CdcReportBuilder
from Carteira import CarteiraBase

class MockCarteira(CarteiraBase):
    """Implementação mock da CarteiraBase para testes dos builders."""
    def __init__(self):
        super().__init__("mock_path.xlsx")
        # Preenchendo as propriedades esperadas pelos builders
        self.data = date(2023, 10, 1)
        self.patrimonio_total = 1500000.00
        self.saldo_tesouraria = 50000.00
        self.valor_di = 10000.00
        
        self.valor_administracao = 100.0
        self.valor_taxa_custodia = 50.0
        self.valor_taxa_gestao = 200.0
        self.valor_taxa_auditoria = 30.0
        self.valor_taxa_cvm = 10.0
        self.valor_anbima = 5.0
        self.valor_taxa_performance = 0.0
        self.outros_valores_receber = 1000.0
        self.outros_valores_pagar = -500.0
        
        self.a_vencer = 500000.0
        self.vencido = 100000.0
        self.pdd = -50000.0
        
        self.df_contas_filtrado = pd.DataFrame()
        self.df_contas_receber_filtrado = pd.DataFrame()
        self.df_cotas_superiores = pd.DataFrame(columns=["CATEGORIA", "Ordem", "Quantidade", "PU Mercado", "Valor Líquido", "Valor Total"])
        
        # Mocks para o extrator
        self.mock_valores = {
            "Total A Pagar": -5000.00,
            "Total A Receber": 15000.00,
            "Cotas Fidara": 200000.00,
            "Cotas CDC": 300000.00,
        }
        
    def carregar_dados(self, aba: str = "CD_ATUAL") -> None:
        pass
        
    def _processar_planilha(self, aba: str = "CD_ATUAL") -> dict:
        return {}
        
    def recuperar_valor_carteira(self, categoria: str, nome_secao: str, coluna_valor: str = "Valor", coluna_descricao: str = "Código", busca_parcial: bool = False) -> float:
        # Simula a busca de valor retornando do dicionário ou 0
        return self.mock_valores.get(categoria, 0.0)

    def recuperar_contas(self, filtro: str, df: pd.DataFrame) -> float:
        return 0.0

class TestFidaraReportBuilder:
    def test_construir_mapeamento_cd(self):
        carteira = MockCarteira()
        builder = FidaraReportBuilder()
        
        resultado = builder.construir_mapeamento_cd(carteira)
        
        # O construtor tem que retornar uma lista de dicionários
        assert isinstance(resultado, list)
        
        # Fidara tem CD? Vamos ver o que gera. Geralmente retorna Patrimonio, Tesouraria, etc
        assert any(item["Valor"] == 1500000.00 for item in resultado) # Patrimonio
        assert any(item["Valor"] == 50000.00 for item in resultado) # Tesouraria

    def test_construir_mapeamento_mec(self):
        carteira = MockCarteira()
        builder = FidaraReportBuilder()
        
        resultado = builder.construir_mapeamento_mec(carteira)
        assert isinstance(resultado, list)

class TestCdcReportBuilder:
    def test_construir_mapeamento_cd(self):
        carteira = MockCarteira()
        builder = CdcReportBuilder()
        
        resultado = builder.construir_mapeamento_cd(carteira)
        assert isinstance(resultado, list)
        assert any(item["Valor"] == 1500000.00 for item in resultado) # Patrimonio

    def test_construir_mapeamento_mec(self):
        carteira = MockCarteira()
        builder = CdcReportBuilder()
        resultado = builder.construir_mapeamento_mec(carteira)
        assert isinstance(resultado, list)
