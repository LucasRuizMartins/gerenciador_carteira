"""
Testes unitários para o mapeamento COBUCCIO_FIDC.

Verifica que:
1. O JSON é válido e carregável pelo schema Pydantic.
2. A fonte soma_secao funciona corretamente.
3. As taxas (administração, gestão, etc.) são recuperadas via atributos.
4. O Senior é recuperado via custom resolver (resolver_cobuccio_senior).
5. Over/NTN/LFTO são somados via soma_secao.
6. As categorias do CD e MEC estão completas.
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
def carteira_cobuccio():
    """Mock de carteira com estrutura da CarteiraSingulareQI."""
    m = MagicMock()

    # Data e patrimônio
    m.data = date(2025, 5, 30)
    m.patrimonio_total = 50_000_000.0
    m.saldo_tesouraria = 1_200_000.0
    m.pdd = -500_000.0

    # Taxas (populadas via _popular_taxas com coluna CATEGORIA/Valor)
    m.valor_administracao = -15_000.0
    m.valor_taxa_gestao = -25_000.0
    m.valor_taxa_custodia = -5_000.0
    m.valor_taxa_auditoria = -3_000.0
    m.valor_taxa_cvm = -1_000.0
    m.valor_selic = -800.0
    m.valor_cetip = -600.0
    m.valor_liq_banco = -500.0
    m.valor_anbima = 0.0
    m.valor_taxa_performance = 0.0

    # _dataframes: simulando as seções da planilha Singulare
    m._dataframes = {
        "ccven": pd.DataFrame({"Valor Líquido": [10_000_000.0, 5_000_000.0]}),      # 15M a vencer
        "vccri": pd.DataFrame({"Valor Líquido": [500_000.0, 300_000.0]}),             # 800K vencidos
        "ntn": pd.DataFrame({"Valor Líquido": [2_000_000.0, 1_500_000.0]}),           # 3.5M NTN-B
        "ltno": pd.DataFrame({"Valor Líquido": [1_000_000.0]}),                       # 1M ltno
        "ntn o": pd.DataFrame({"Valor Líquido": [800_000.0]}),                        # 800K ntn o
        "lfto": pd.DataFrame({"Valor Líquido": [700_000.0]}),                         # 700K lfto
        "outros_fundos": pd.DataFrame({"Valor Líquido": [3_000_000.0]}),              # GV Cash
        "tesouraria": pd.DataFrame({"Valor": [1_200_000.0]}),
        "senior": pd.DataFrame({
            "CATEGORIA": ["Senior 1", "Senior 2", "Senior 3"],
            "Valor Bruto": [10_000_000.0, 5_000_000.0, 3_000_000.0],
            "PU Mercado": [1000.12, 1000.34, 999.87],
        }),
    }

    # df_contas_filtrado (resultado de _agrupar_contas com CATEGORIA/Valor)
    m.df_contas_filtrado = pd.DataFrame({
        "CATEGORIA": ["Administração", "Gestão", "Auditoria", "Custódia", "CVM",
                      "SELIC", "CETIP", "Banco Liquidante", "Contas a pagar"],
        "Valor": [-15_000.0, -25_000.0, -3_000.0, -5_000.0, -1_000.0,
                  -800.0, -600.0, -500.0, -2_000.0],
    })

    # df_senior via atributo direto
    m.df_senior = m._dataframes["senior"]

    # recuperar_valor_carteira — para Qtd Cota e Vlr Cota
    def mock_recuperar(chave, coluna):
        if chave == "Qtd Cota" and coluna == 1:
            return 42_000.0
        if chave == "Vlr Cota" and coluna == 1:
            return 1_190.45
        if chave == "COBUAVE" and coluna == "Valor Líquido":
            return 15_000_000.0
        if chave == "COBUVENC" and coluna == "Valor Líquido":
            return 800_000.0
        return 0.0
    m.recuperar_valor_carteira.side_effect = mock_recuperar

    # recuperar_contas — busca no df_contas_filtrado
    def mock_recuperar_contas(filtro, df):
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
# Testes de estrutura do JSON
# ===========================================================================

class TestCobuccioJsonValido:
    """Verifica que o JSON é válido e bem estruturado."""

    def test_carregavel_pelo_schema(self):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        assert builder.fundo == "COBUCCIO_FIDC"
        assert builder.administradora == "SINGULARE"

    def test_mapeamento_cd_nao_vazio(self):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        assert len(builder._config.mapeamento_cd) > 0

    def test_mapeamento_mec_nao_vazio(self):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        assert len(builder._config.mapeamento_mec) > 0

    def test_data_base_presente_cd(self):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        cats = [i.categoria for i in builder._config.mapeamento_cd]
        assert "Data-Base" in cats

    def test_data_presente_mec(self):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        cats = [i.categoria for i in builder._config.mapeamento_mec]
        assert "DATA" in cats

    def test_soma_secao_ntn_configurado(self):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        item_ntn = next(
            (i for i in builder._config.mapeamento_cd if i.categoria == "NTN-B"),
            None
        )
        assert item_ntn is not None
        assert item_ntn.fonte == "soma_secao"
        assert item_ntn.secao == "ntn"
        assert item_ntn.coluna == "Valor Líquido"

    def test_over_usa_soma_secao(self):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        overs = [i for i in builder._config.mapeamento_cd if i.categoria == "Over/Compromissada"]
        assert len(overs) == 3  # ltno, ntn o, lfto
        for item in overs:
            assert item.fonte == "soma_secao"
            assert item.coluna == "Valor Líquido"
        secoes = {i.secao for i in overs}
        assert "ltno" in secoes
        assert "ntn o" in secoes
        assert "lfto" in secoes


# ===========================================================================
# Testes do resolver soma_secao
# ===========================================================================

class TestSomaSecao:
    """Testa o resolver soma_secao do MappingEngine diretamente."""

    def test_soma_secao_ntn(self, carteira_cobuccio):
        """NTN-B deve somar a coluna Valor Líquido da seção 'ntn'."""
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_cd(carteira_cobuccio)
        ntn_val = next(r["Valor"] for r in resultado if r["Categoria"] == "NTN-B")
        assert abs(ntn_val - 3_500_000.0) < 1.0  # 2M + 1.5M

    def test_soma_secao_over_total(self, carteira_cobuccio):
        """Over/Compromissada deve somar ltno + ntn o + lfto = 2.5M."""
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_cd(carteira_cobuccio)
        over_val = next(r["Valor"] for r in resultado if r["Categoria"] == "Over/Compromissada")
        # ltno=1M + ntn o=800K + lfto=700K = 2.5M (MappingEngine soma acumulando)
        assert abs(over_val - 2_500_000.0) < 1.0

    def test_soma_secao_ccven(self, carteira_cobuccio):
        """Direitos a Vencer deve somar seção ccven = 15M."""
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_cd(carteira_cobuccio)
        avencer = next(r["Valor"] for r in resultado if r["Categoria"] == "Direitos Creditórios a Vencer")
        assert abs(avencer - 15_000_000.0) < 1.0

    def test_soma_secao_secao_vazia_retorna_zero(self):
        """Seção vazia ou inexistente deve retornar 0.0."""
        engine = MappingEngine()

        class FakeItem:
            categoria = "Teste"
            fonte = "soma_secao"
            secao = "nao_existe"
            coluna = "Valor Líquido"

        m = MagicMock()
        m._dataframes = {}
        result = engine._resolver_soma_secao(m, FakeItem())
        assert result == 0.0


# ===========================================================================
# Testes das taxas
# ===========================================================================

class TestTaxasCobuccio:
    """Verifica que as taxas são recuperadas corretamente via atributos."""

    def test_taxa_administracao(self, carteira_cobuccio):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_cd(carteira_cobuccio)
        adm = next(r["Valor"] for r in resultado if r["Categoria"] == "Taxa de Administração")
        assert adm == -15_000.0

    def test_taxa_gestao(self, carteira_cobuccio):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_cd(carteira_cobuccio)
        gestao = next(r["Valor"] for r in resultado if r["Categoria"] == "Taxa de Gestão")
        assert gestao == -25_000.0

    def test_taxa_custodia(self, carteira_cobuccio):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_cd(carteira_cobuccio)
        custodia = next(r["Valor"] for r in resultado if r["Categoria"] == "Taxa de Custódia")
        assert custodia == -5_000.0

    def test_taxa_selic(self, carteira_cobuccio):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_cd(carteira_cobuccio)
        selic = next(r["Valor"] for r in resultado if r["Categoria"] == "TAXA SELIC")
        assert selic == -800.0

    def test_taxa_cetip(self, carteira_cobuccio):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_cd(carteira_cobuccio)
        cetip = next(r["Valor"] for r in resultado if r["Categoria"] == "TAXA CETIP")
        assert cetip == -600.0

    def test_banco_liquidante(self, carteira_cobuccio):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_cd(carteira_cobuccio)
        banco = next(r["Valor"] for r in resultado if r["Categoria"] == "Banco Liquidante")
        assert banco == -500.0


# ===========================================================================
# Testes do Senior
# ===========================================================================

class TestSeniorCobuccio:
    """Verifica que as cotas sênior são recuperadas via resolver_cobuccio_senior."""

    def test_senior_valor_total(self, carteira_cobuccio):
        """Senior (-) deve somar Valor Bruto de todas as séries."""
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_cd(carteira_cobuccio)
        senior = next(r["Valor"] for r in resultado if r["Categoria"] == "Senior (-)")
        assert abs(senior - 18_000_000.0) < 1.0  # 10M + 5M + 3M

    def test_cota_senior_1_mec(self, carteira_cobuccio):
        """COTA SENIOR 1 no MEC deve retornar PU Mercado do Senior 1."""
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_mec(carteira_cobuccio)
        cota_s1 = next(r["Valor"] for r in resultado if r["Categoria"] == "COTA SENIOR 1")
        assert abs(cota_s1 - 1000.12) < 0.01

    def test_cota_senior_3_mec(self, carteira_cobuccio):
        """COTA SENIOR 3 no MEC deve retornar PU Mercado do Senior 3."""
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_mec(carteira_cobuccio)
        cota_s3 = next(r["Valor"] for r in resultado if r["Categoria"] == "COTA SENIOR 3")
        assert abs(cota_s3 - 999.87) < 0.01


# ===========================================================================
# Teste de integração — CD e MEC completos
# ===========================================================================

class TestCobuccioCompleto:
    """Verifica completude e consistência do CD e MEC."""

    def test_cd_tem_patrimonio_total(self, carteira_cobuccio):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_cd(carteira_cobuccio)
        pl = next(r["Valor"] for r in resultado if r["Categoria"] == "PL Carteira Subordinada")
        assert pl == 50_000_000.0

    def test_cd_tem_pdd(self, carteira_cobuccio):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_cd(carteira_cobuccio)
        pdd = next(r["Valor"] for r in resultado if r["Categoria"] == "PDD - Prov. de Perdas")
        assert pdd == -500_000.0

    def test_mec_quant_cotas(self, carteira_cobuccio):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_mec(carteira_cobuccio)
        qtd = next(r["Valor"] for r in resultado if r["Categoria"] == "QUANT COTAS")
        assert qtd == 42_000.0

    def test_mec_cota_subordinada(self, carteira_cobuccio):
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        resultado = builder.construir_mapeamento_mec(carteira_cobuccio)
        cota = next(r["Valor"] for r in resultado if r["Categoria"] == "COTA SUBORDINADA")
        assert cota == 1_190.45

    def test_cd_sem_erros_criticos(self, carteira_cobuccio):
        """Nenhum erro crítico deve aparecer no CD."""
        builder = ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json")
        carteira_cobuccio.warnings = []
        builder.construir_mapeamento_cd(carteira_cobuccio)
        erros = [w for w in carteira_cobuccio.warnings if "Erro crítico" in w]
        assert len(erros) == 0, f"Erros críticos encontrados: {erros}"
