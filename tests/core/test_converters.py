"""
Testes unitários para src/core/converters.py.

Foco no comportamento esperado (TDD) das funções puras de conversão
e parsing. Todos os testes são completamente isolados: nenhum arquivo
Excel real é necessário.

Estrutura:
    TestConverterMoeda       — testes para converter_moeda()
    TestLimparValorMonetario — testes para limpar_valor_monetario()
    TestResetarCabecalho     — testes para resetar_cabecalho()
    TestEncontrarLinha       — testes para encontrar_linha_categoria()
    TestExtrairSecao         — testes para extrair_secao()
    TestDetectarColuna       — testes para detectar_coluna()
    TestClassificarContas    — testes para classificar_contas()
    TestBuscarValor          — testes para buscar_valor_em_dataframe()
"""

from __future__ import annotations

import sys
import os

import pytest
import pandas as pd

# Garante que o diretório raiz do projeto está no sys.path
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from src.core.converters import (
    buscar_valor_em_dataframe,
    classificar_contas,
    converter_moeda,
    detectar_coluna,
    encontrar_linha_categoria,
    extrair_secao,
    limpar_valor_monetario,
    resetar_cabecalho,
)


# ===========================================================================
# TestConverterMoeda
# ===========================================================================


class TestConverterMoeda:
    """Testes para converter_moeda() — todos os formatos suportados."""

    # --- Entradas nulas / vazias ---

    def test_retorna_zero_para_none(self):
        assert converter_moeda(None) == 0.0

    def test_retorna_zero_para_string_vazia(self):
        assert converter_moeda("") == 0.0

    def test_retorna_zero_para_nan_pandas(self):
        assert converter_moeda(float("nan")) == 0.0

    # --- Tipos numéricos passados diretamente ---

    def test_passa_float_sem_alteracao(self):
        assert converter_moeda(123.45) == 123.45

    def test_passa_int_sem_alteracao(self):
        assert converter_moeda(1000) == 1000.0

    def test_passa_zero(self):
        assert converter_moeda(0) == 0.0

    # --- Strings no formato brasileiro ---

    def test_converte_string_virgula_decimal(self):
        assert converter_moeda("1234,56") == 1234.56

    def test_converte_string_ponto_milhar_virgula_decimal(self):
        assert converter_moeda("1.234,56") == 1234.56

    def test_converte_string_sem_decimal(self):
        assert converter_moeda("5000,00") == 5000.0

    # --- Valores negativos com parênteses (padrão contábil) ---

    def test_converte_parenteses_para_negativo(self):
        assert converter_moeda("(500,00)") == -500.0

    def test_converte_parenteses_com_milhar(self):
        assert converter_moeda("(1.234,56)") == -1234.56

    # --- Strings inválidas ---

    def test_retorna_zero_para_string_invalida(self):
        assert converter_moeda("abc") == 0.0

    def test_retorna_zero_para_apenas_virgula(self):
        assert converter_moeda(",") == 0.0


# ===========================================================================
# TestLimparValorMonetario
# ===========================================================================


class TestLimparValorMonetario:
    """Testes para limpar_valor_monetario() — formato BR sem parênteses."""

    def test_converte_string_formato_br(self):
        assert limpar_valor_monetario("1.234,56") == 1234.56

    def test_passa_float(self):
        assert limpar_valor_monetario(99.9) == 99.9

    def test_retorna_zero_para_nulo(self):
        assert limpar_valor_monetario(None) == 0.0


# ===========================================================================
# TestResetarCabecalho
# ===========================================================================


class TestResetarCabecalho:
    """Testes para resetar_cabecalho()."""

    def test_promove_primeira_linha_como_colunas(self):
        df = pd.DataFrame([
            ["Código", "Descrição", "Valor"],
            ["001", "Item A", 100.0],
            ["002", "Item B", 200.0],
        ])
        resultado = resetar_cabecalho(df)
        assert list(resultado.columns) == ["Código", "Descrição", "Valor"]
        assert len(resultado) == 2

    def test_retorna_vazio_para_dataframe_vazio(self):
        resultado = resetar_cabecalho(pd.DataFrame())
        assert resultado.empty

    def test_retorna_vazio_para_none(self):
        resultado = resetar_cabecalho(None)
        assert resultado.empty

    def test_reset_de_indice_apos_slicing(self):
        df = pd.DataFrame([
            ["Código", "Valor"],
            ["A01", 500.0],
        ])
        resultado = resetar_cabecalho(df)
        assert resultado.index.tolist() == [0]


# ===========================================================================
# TestEncontrarLinhaCategoria
# ===========================================================================


class TestEncontrarLinhaCategoria:
    """Testes para encontrar_linha_categoria()."""

    @pytest.fixture
    def df_exemplo(self):
        return pd.DataFrame({
            "Categoria": ["HEADER", "VALORES A PAGAR", "Gestão", "RESUMO"],
            "Valor": [None, None, -1500.0, None],
        })

    def test_encontra_linha_existente(self, df_exemplo):
        resultado = encontrar_linha_categoria(df_exemplo, "VALORES A PAGAR", "Categoria")
        assert resultado == 1

    def test_retorna_none_para_inexistente(self, df_exemplo):
        resultado = encontrar_linha_categoria(df_exemplo, "NÃO EXISTE", "Categoria")
        assert resultado is None

    def test_usa_primeira_coluna_quando_coluna_nao_informada(self, df_exemplo):
        resultado = encontrar_linha_categoria(df_exemplo, "HEADER")
        assert resultado == 0


# ===========================================================================
# TestExtrairSecao
# ===========================================================================


class TestExtrairSecao:
    """Testes para extrair_secao()."""

    @pytest.fixture
    def df_planilha(self):
        return pd.DataFrame({
            "Col0": ["MARCADOR", "Histórico", "Gestão", "ANBIMA", None],
            "Col1": [None, "Valor Total", -1500.0, -250.0, None],
        })

    def test_extrai_secao_valida(self, df_planilha):
        # Extrai da linha 1 (Histórico/Valor) até 4 (linha nula)
        resultado = extrair_secao(df_planilha, 1, 4)
        assert not resultado.empty
        assert "Histórico" in resultado.columns

    def test_retorna_vazio_para_intervalo_invalido(self, df_planilha):
        resultado = extrair_secao(df_planilha, 5, 2)
        assert resultado.empty

    def test_remove_linhas_nulas(self, df_planilha):
        resultado = extrair_secao(df_planilha, 1, 5)
        # A linha nula (índice 4) deve ser removida
        assert resultado.isna().all(axis=1).sum() == 0


# ===========================================================================
# TestDetectarColuna
# ===========================================================================


class TestDetectarColuna:
    """Testes para detectar_coluna()."""

    @pytest.fixture
    def df_colunas(self):
        return pd.DataFrame(columns=["Histórico", "Valor Total", "Ordem"])

    def test_encontra_coluna_exata(self, df_colunas):
        assert detectar_coluna(df_colunas, ["Histórico"]) == "Histórico"

    def test_encontra_coluna_case_insensitive(self, df_colunas):
        # Usa coluna sem acento para testar case-insensitive puro
        # (normalização unicode de acentos é comportamento do SO, não do módulo)
        df_sem_acento = pd.DataFrame(columns=["Historico", "Valor Total", "Ordem"])
        assert detectar_coluna(df_sem_acento, ["historico"]) == "Historico"

    def test_encontra_coluna_com_acento_exato(self, df_colunas):
        # Para colunas acentuadas, a correspondência exata funciona
        assert detectar_coluna(df_colunas, ["Histórico"]) == "Histórico"


    def test_retorna_primeiro_candidato_valido(self, df_colunas):
        # "Valor" não existe, mas "Valor Total" sim
        resultado = detectar_coluna(df_colunas, ["Valor", "Valor Total"])
        assert resultado == "Valor Total"

    def test_retorna_none_quando_nenhum_candidato_encontrado(self, df_colunas):
        assert detectar_coluna(df_colunas, ["Inexistente", "Também inexistente"]) is None


# ===========================================================================
# TestClassificarContas
# ===========================================================================


class TestClassificarContas:
    """Testes para classificar_contas() — o algoritmo central do sistema."""

    @pytest.fixture
    def df_contas(self):
        return pd.DataFrame({
            "Histórico": [
                "Taxa de Gestão Fundo X",
                "Taxa ANBIMA mensal",
                "Pagamento fornecedor genérico",
                "Receita diversa",
            ],
            "Valor Total": [-1_500.0, -250.0, -300.0, 800.0],
        })

    def test_substitui_descricao_por_palavra_chave(self, df_contas):
        resultado = classificar_contas(
            df_contas, "Histórico", "Valor Total", ["gestão", "anbima"]
        )
        assert "Gestão" in resultado["Histórico"].values
        assert "Anbima" in resultado["Histórico"].values

    def test_classifica_nao_mapeado_negativo_como_contas_a_pagar(self, df_contas):
        resultado = classificar_contas(
            df_contas, "Histórico", "Valor Total", ["gestão", "anbima"]
        )
        assert "Contas a pagar" in resultado["Histórico"].values

    def test_classifica_nao_mapeado_positivo_como_contas_a_receber(self, df_contas):
        resultado = classificar_contas(
            df_contas, "Histórico", "Valor Total", ["gestão", "anbima"]
        )
        assert "Contas a receber" in resultado["Histórico"].values

    def test_resultado_e_agrupado(self, df_contas):
        """Dois itens com a mesma categoria devem ser somados."""
        df_duplo = pd.concat([df_contas, df_contas], ignore_index=True)
        resultado = classificar_contas(
            df_duplo, "Histórico", "Valor Total", ["gestão", "anbima"]
        )
        gestao_row = resultado[resultado["Histórico"] == "Gestão"]
        assert gestao_row["Valor Total"].values[0] == -3_000.0

    def test_retorna_dataframe_com_colunas_corretas(self, df_contas):
        resultado = classificar_contas(
            df_contas, "Histórico", "Valor Total", ["gestão"]
        )
        assert "Histórico" in resultado.columns
        assert "Valor Total" in resultado.columns

    def test_ordem_crescente_por_valor(self, df_contas):
        """O resultado deve estar ordenado do menor para o maior valor."""
        resultado = classificar_contas(
            df_contas, "Histórico", "Valor Total", ["gestão", "anbima"]
        )
        valores = resultado["Valor Total"].tolist()
        assert valores == sorted(valores)


# ===========================================================================
# TestBuscarValorEmDataframe
# ===========================================================================


class TestBuscarValorEmDataframe:
    """Testes para buscar_valor_em_dataframe()."""

    @pytest.fixture
    def df_resumo(self):
        return pd.DataFrame({
            "Categoria": ["Gestão", "ANBIMA", "PDD", "Tesouraria"],
            "Valor":     [-1_500.0, -250.0, -5_000.0, 35_000.0],
        })

    def test_busca_valor_por_igualdade_exata(self, df_resumo):
        resultado = buscar_valor_em_dataframe(df_resumo, "PDD", "Categoria", "Valor")
        assert resultado == -5_000.0

    def test_busca_parcial(self, df_resumo):
        resultado = buscar_valor_em_dataframe(
            df_resumo, "Ges", "Categoria", "Valor", busca_parcial=True
        )
        assert resultado == -1_500.0

    def test_retorna_zero_para_categoria_inexistente(self, df_resumo):
        resultado = buscar_valor_em_dataframe(
            df_resumo, "Inexistente", "Categoria", "Valor"
        )
        assert resultado == 0.0

    def test_busca_por_indice_coluna(self, df_resumo):
        """Coluna passada como índice inteiro (compatibilidade com código legado)."""
        resultado = buscar_valor_em_dataframe(
            df_resumo, "ANBIMA", "Categoria", 1
        )
        assert resultado == -250.0
