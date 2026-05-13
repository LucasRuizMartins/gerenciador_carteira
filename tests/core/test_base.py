"""
Testes unitários para CarteiraBase (src/core/base via Carteira.py).

Verifica o contrato da classe base abstrata, seus atributos de inicialização,
validações e métodos utilitários compartilhados — sem carregar nenhum arquivo Excel.
"""

from __future__ import annotations

import sys
import os

import pytest
import pandas as pd

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from Carteira import CarteiraBase


# ---------------------------------------------------------------------------
# Implementação concreta mínima para testar a classe abstrata
# ---------------------------------------------------------------------------


class CarteiraConcreta(CarteiraBase):
    """Subclasse mínima de CarteiraBase usada exclusivamente em testes."""

    def carregar_dados(self, aba: str = "CD_ATUAL") -> None:
        pass

    def _processar_planilha(self, aba: str = "CD_ATUAL") -> dict:
        return {}


# ===========================================================================
# TestInicializacao
# ===========================================================================


class TestInicializacao:
    """Verifica que CarteiraBase inicializa todos os atributos corretamente."""

    def test_path_nulo_por_padrao(self):
        c = CarteiraConcreta()
        assert c.path_carteira is None

    def test_path_definido_via_construtor(self):
        c = CarteiraConcreta("/caminho/carteira.xlsx")
        assert c.path_carteira == "/caminho/carteira.xlsx"

    def test_patrimonio_inicial_zero(self):
        assert CarteiraConcreta().patrimonio_total == 0.0

    def test_saldo_tesouraria_inicial_zero(self):
        assert CarteiraConcreta().saldo_tesouraria == 0.0

    def test_pdd_inicial_zero(self):
        assert CarteiraConcreta().pdd == 0.0

    def test_taxas_iniciais_zero(self):
        c = CarteiraConcreta()
        assert c.valor_administracao == 0.0
        assert c.valor_anbima == 0.0
        assert c.valor_taxa_gestao == 0.0
        assert c.valor_taxa_custodia == 0.0
        assert c.valor_taxa_cvm == 0.0
        assert c.valor_taxa_auditoria == 0.0
        assert c.valor_taxa_performance == 0.0

    def test_lista_codigos_contas_pagar_vazia(self):
        assert CarteiraConcreta().codigos_contas_pagar == []

    def test_dataframes_internos_vazio(self):
        assert CarteiraConcreta()._dataframes == {}

    def test_data_nula(self):
        assert CarteiraConcreta().data is None


# ===========================================================================
# TestValidarPath
# ===========================================================================


class TestValidarPath:
    """Testes para o método _validar_path()."""

    def test_levanta_excecao_quando_path_nulo(self):
        c = CarteiraConcreta()
        with pytest.raises(ValueError, match="Caminho da carteira não definido"):
            c._validar_path()

    def test_levanta_excecao_quando_path_string_vazia(self):
        c = CarteiraConcreta("")
        with pytest.raises(ValueError):
            c._validar_path()

    def test_nao_levanta_excecao_com_path_valido(self):
        c = CarteiraConcreta("/qualquer/caminho.xlsx")
        c._validar_path()  # Não deve levantar exceção


# ===========================================================================
# TestAcrescentarContasPagar
# ===========================================================================


class TestAcrescentarContasPagar:
    """Testes para acrescentar_contas_pagar()."""

    def test_acrescenta_codigo_unico(self):
        c = CarteiraConcreta()
        c.acrescentar_contas_pagar("Gestão")
        assert "Gestão" in c.codigos_contas_pagar

    def test_acrescenta_multiplos_codigos(self):
        c = CarteiraConcreta()
        c.acrescentar_contas_pagar("Gestão", "ANBIMA", "Auditoria")
        assert len(c.codigos_contas_pagar) == 3

    def test_chamadas_sucessivas_acumulam(self):
        c = CarteiraConcreta()
        c.acrescentar_contas_pagar("Gestão")
        c.acrescentar_contas_pagar("ANBIMA")
        assert len(c.codigos_contas_pagar) == 2

    def test_listas_sao_independentes_entre_instancias(self):
        """Garante que a lista não é compartilhada entre instâncias (bug de mutável no __init__)."""
        c1 = CarteiraConcreta()
        c2 = CarteiraConcreta()
        c1.acrescentar_contas_pagar("Gestão")
        assert c2.codigos_contas_pagar == []


# ===========================================================================
# TestAcessoDataframes
# ===========================================================================


class TestAcessoDataframes:
    """Testes para o método df() de acesso seguro a DataFrames internos."""

    def test_retorna_dataframe_vazio_para_chave_inexistente(self):
        c = CarteiraConcreta()
        resultado = c.df("chave_que_nao_existe")
        assert isinstance(resultado, pd.DataFrame)
        assert resultado.empty

    def test_retorna_dataframe_correto_para_chave_existente(self):
        c = CarteiraConcreta()
        df_esperado = pd.DataFrame({"A": [1, 2]})
        c._dataframes["renda_fixa"] = df_esperado
        resultado = c.df("renda_fixa")
        assert resultado.equals(df_esperado)


# ===========================================================================
# TestRepr
# ===========================================================================


class TestRepr:
    """Testes para __repr__()."""

    def test_repr_contem_nome_da_classe(self):
        c = CarteiraConcreta()
        assert "CarteiraConcreta" in repr(c)

    def test_repr_contem_patrimonio(self):
        c = CarteiraConcreta()
        c.patrimonio_total = 1_000_000.0
        assert "1" in repr(c)  # Ao menos parte do número aparece
