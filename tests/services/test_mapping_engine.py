"""
Testes unitários para MappingEngine e ConfigDrivenBuilder.

Testa cada tipo de fonte de forma isolada usando objetos mock simples.
Nenhum arquivo Excel real é necessário — tudo com mocks inlineados.

Cobertura:
    - MappingEngine._resolver_atributo
    - MappingEngine._resolver_taxa
    - MappingEngine._resolver_valor_carteira
    - MappingEngine._resolver_cotas (soma e primeiro)
    - MappingEngine._resolver_contas (pagar e receber)
    - MappingEngine._resolver_fixo
    - MappingEngine._resolver_custom
    - MappingEngine.resolver (integração de múltiplos itens)
    - MappingEngine.resolver (tratamento de erro por item)
    - ConfigDrivenBuilder.de_dict
    - ConfigDrivenBuilder.de_arquivo (arquivo inexistente)
    - ConfigDrivenBuilder.registrar_custom (fluent API)
    - Schema Pydantic: validação de campos obrigatórios por fonte
    - Schema Pydantic: categorias duplicadas
"""

from __future__ import annotations

import sys
import os
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Garante que a raiz do projeto está no path
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from src.services.mapping_engine import MappingEngine
from src.services.config_driven_builder import ConfigDrivenBuilder
from src.config.schemas import ItemMapeamento, MapeamentoFundo


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def engine() -> MappingEngine:
    return MappingEngine()


@pytest.fixture
def carteira_mock():
    """Carteira mock com todos os atributos padrão populados."""
    m = MagicMock()
    m.data = date(2024, 12, 31)
    m.patrimonio_total = 1_500_000.0
    m.saldo_tesouraria = 50_000.0
    m.a_vencer = 800_000.0
    m.vencido = 100_000.0
    m.pdd = -30_000.0
    m.valor_di = 20_000.0
    m.valor_administracao = -1_000.0
    m.valor_taxa_gestao = -2_000.0
    m.valor_taxa_cvm = -500.0
    m.valor_taxa_auditoria = -300.0
    m.valor_taxa_custodia = -200.0
    m.valor_anbima = -100.0
    m.valor_taxa_performance = 0.0
    m.valor_selic = 0.0
    m.valor_cetip = 0.0
    m.valor_liq_banco = 0.0
    m.outros_valores_pagar = -5_000.0
    m.outros_valores_receber = 3_000.0

    # df_cotas_superiores com colunas "Ordem", "Valor Total", "Qtde. Total", "Valor Cota"
    m.df_cotas_superiores = pd.DataFrame({
        "Ordem": [99, 98, 97],
        "Valor Total": [100_000.0, 80_000.0, 60_000.0],
        "Qtde. Total": [1_000.0, 800.0, 600.0],
        "Valor Cota": [1.5, 1.4, 1.3],
    })

    # df_contas_filtrado (contas a pagar)
    m.df_contas_filtrado = pd.DataFrame({
        "Histórico": ["Anbima", "Contas a pagar", "Cvm"],
        "Valor Total": [-100.0, -500.0, -50.0],
    })

    # df_contas_receber_filtrado (contas a receber / diferimentos)
    m.df_contas_receber_filtrado = pd.DataFrame({
        "Histórico": ["Anbima", "Cvm", "Contas a receber"],
        "Valor Total": [80.0, 40.0, 200.0],
    })

    # recuperar_valor_carteira retorna valores baseados na chave
    def mock_recuperar(chave, coluna):
        valores = {
            ("GRUPO MPR PARTICIP", 8): 999_000.0,
            ("Qtde. Cota", 1): 500_000.0,
            ("Valor da Cota Líquida", 1): "1,234567",
            ("A VENCER", 2): 800_000.0,
        }
        return valores.get((chave, coluna), 0.0)

    m.recuperar_valor_carteira.side_effect = mock_recuperar

    # recuperar_contas retorna valores baseados no filtro
    def mock_recuperar_contas(filtro, df):
        if df is None or df.empty:
            return 0.0
        col_desc = df.columns[0]
        col_val = df.columns[1]
        filtro_mask = df[col_desc].str.contains(filtro, case=False, na=False)
        resultado = df.loc[filtro_mask, col_val]
        return float(resultado.values[0]) if not resultado.empty else 0.0

    m.recuperar_contas.side_effect = mock_recuperar_contas

    return m


# ===========================================================================
# Testes de cada resolver individual
# ===========================================================================


class TestResolverAtributo:
    def test_lê_atributo_existente(self, engine, carteira_mock):
        item = ItemMapeamento(categoria="Data-Base", fonte="atributo", campo="data")
        resultado = engine._resolver_atributo(carteira_mock, item)
        assert resultado == date(2024, 12, 31)

    def test_lê_patrimonio(self, engine, carteira_mock):
        item = ItemMapeamento(categoria="PL", fonte="atributo", campo="patrimonio_total")
        resultado = engine._resolver_atributo(carteira_mock, item)
        assert resultado == 1_500_000.0

    def test_retorna_zero_para_atributo_inexistente(self, engine, carteira_mock):
        del carteira_mock.campo_que_nao_existe
        item = ItemMapeamento(
            categoria="X", fonte="atributo", campo="campo_que_nao_existe"
        )
        # getattr com None para atributo inexistente via MagicMock
        carteira_mock.campo_que_nao_existe = None
        resultado = engine._resolver_atributo(carteira_mock, item)
        assert resultado == 0.0


class TestResolverTaxa:
    def test_lê_taxa_administracao(self, engine, carteira_mock):
        item = ItemMapeamento(
            categoria="Taxa de Administração", fonte="taxa", campo="valor_administracao"
        )
        resultado = engine._resolver_taxa(carteira_mock, item)
        assert resultado == -1_000.0

    def test_lê_taxa_gestao(self, engine, carteira_mock):
        item = ItemMapeamento(
            categoria="Taxa de Gestão", fonte="taxa", campo="valor_taxa_gestao"
        )
        resultado = engine._resolver_taxa(carteira_mock, item)
        assert resultado == -2_000.0


class TestResolverValorCarteira:
    def test_recupera_valor_por_chave(self, engine, carteira_mock):
        item = ItemMapeamento(
            categoria="MPR",
            fonte="valor_carteira",
            chave_etl="GRUPO MPR PARTICIP",
            coluna=8,
        )
        resultado = engine._resolver_valor_carteira(carteira_mock, item)
        assert resultado == 999_000.0

    def test_retorna_zero_para_chave_inexistente(self, engine, carteira_mock):
        item = ItemMapeamento(
            categoria="X",
            fonte="valor_carteira",
            chave_etl="CHAVE QUE NAO EXISTE",
            coluna=5,
        )
        resultado = engine._resolver_valor_carteira(carteira_mock, item)
        assert resultado == 0.0


class TestResolverCotas:
    @patch("src.services.mapping_engine.obter_valor_ordem",
           side_effect=lambda df, o, c: {99: 100_000.0, 98: 80_000.0, 97: 60_000.0}.get(o, 0.0))
    def test_soma_multiplas_ordens(self, mock_obter, engine, carteira_mock):
        item = ItemMapeamento(
            categoria="Senior Total",
            fonte="cotas",
            ordens=[99, 98, 97],
            coluna_valor="Valor Total",
            agregacao="soma",
        )
        resultado = engine._resolver_cotas(carteira_mock, item)
        assert resultado == 240_000.0

    @patch("src.services.mapping_engine.obter_valor_ordem", return_value=100_000.0)
    def test_primeiro_retorna_somente_primeiro(self, mock_obter, engine, carteira_mock):
        item = ItemMapeamento(
            categoria="Senior 1",
            fonte="cotas",
            ordens=[99],
            coluna_valor="Valor Total",
            agregacao="primeiro",
        )
        resultado = engine._resolver_cotas(carteira_mock, item)
        assert resultado == 100_000.0

    def test_retorna_zero_sem_df_cotas(self, engine, carteira_mock):
        carteira_mock.df_cotas_superiores = None
        item = ItemMapeamento(
            categoria="X", fonte="cotas", ordens=[99], coluna_valor="Valor Total"
        )
        resultado = engine._resolver_cotas(carteira_mock, item)
        assert resultado == 0.0


class TestResolverContas:
    def test_contas_pagar(self, engine, carteira_mock):
        item = ItemMapeamento(
            categoria="Anbima",
            fonte="contas",
            filtro="Anbima",
            dataframe="df_contas_filtrado",
        )
        resultado = engine._resolver_contas(carteira_mock, item)
        assert resultado == -100.0

    def test_contas_receber(self, engine, carteira_mock):
        item = ItemMapeamento(
            categoria="Diferimento Anbima",
            fonte="contas",
            filtro="Anbima",
            dataframe="df_contas_receber_filtrado",
        )
        resultado = engine._resolver_contas(carteira_mock, item)
        assert resultado == 80.0

    def test_usa_contas_pagar_como_default(self, engine, carteira_mock):
        """dataframe=None deve usar df_contas_filtrado."""
        item = ItemMapeamento(
            categoria="Cvm",
            fonte="contas",
            filtro="Cvm",
        )
        resultado = engine._resolver_contas(carteira_mock, item)
        assert resultado == -50.0

    def test_retorna_zero_se_df_vazio(self, engine, carteira_mock):
        carteira_mock.df_contas_filtrado = pd.DataFrame()
        item = ItemMapeamento(
            categoria="X", fonte="contas", filtro="qualquer"
        )
        resultado = engine._resolver_contas(carteira_mock, item)
        assert resultado == 0.0


class TestResolverFixo:
    def test_retorna_zero(self, engine, carteira_mock):
        item = ItemMapeamento(categoria="X", fonte="fixo", valor_fixo=0)
        assert engine._resolver_fixo(carteira_mock, item) == 0

    def test_retorna_float_constante(self, engine, carteira_mock):
        item = ItemMapeamento(categoria="Subordinação", fonte="fixo", valor_fixo=0.5)
        assert engine._resolver_fixo(carteira_mock, item) == 0.5

    def test_retorna_string(self, engine, carteira_mock):
        item = ItemMapeamento(categoria="X", fonte="fixo", valor_fixo="placeholder")
        assert engine._resolver_fixo(carteira_mock, item) == "placeholder"


class TestResolverCustom:
    def test_chama_funcao_registrada(self, engine, carteira_mock):
        def calcular_especial(carteira, item):
            return 42_000.0

        engine.register_custom_resolver("calcular_especial", calcular_especial)
        item = ItemMapeamento(
            categoria="Especial", fonte="custom", nome_funcao="calcular_especial"
        )
        resultado = engine._resolver_custom(carteira_mock, item)
        assert resultado == 42_000.0

    def test_levanta_erro_se_nao_registrado(self, engine, carteira_mock):
        item = ItemMapeamento(
            categoria="X", fonte="custom", nome_funcao="funcao_inexistente"
        )
        with pytest.raises(ValueError, match="não registrado"):
            engine._resolver_custom(carteira_mock, item)


# ===========================================================================
# Testes de integração do resolver principal
# ===========================================================================


class TestResolverIntegrado:
    def test_retorna_lista_correta(self, engine, carteira_mock):
        itens = [
            ItemMapeamento(categoria="Data-Base", fonte="atributo", campo="data"),
            ItemMapeamento(
                categoria="PL", fonte="atributo", campo="patrimonio_total"
            ),
            ItemMapeamento(categoria="Zero", fonte="fixo", valor_fixo=0),
        ]
        resultado = engine.resolver(carteira_mock, itens)
        assert len(resultado) == 3
        assert resultado[0] == {"Categoria": "Data-Base", "Valor": date(2024, 12, 31)}
        assert resultado[1] == {"Categoria": "PL", "Valor": 1_500_000.0}
        assert resultado[2] == {"Categoria": "Zero", "Valor": 0}

    def test_multiplicador_aplicado(self, engine, carteira_mock):
        itens = [
            ItemMapeamento(
                categoria="Senior (-)",
                fonte="atributo",
                campo="patrimonio_total",
                multiplicador=-1.0,
            )
        ]
        resultado = engine.resolver(carteira_mock, itens)
        assert resultado[0]["Valor"] == -1_500_000.0

    def test_item_com_erro_retorna_zero_e_continua(self, engine, carteira_mock):
        """Um item com erro não deve interromper os demais."""
        carteira_mock.recuperar_valor_carteira.side_effect = Exception("Falha grave")
        itens = [
            ItemMapeamento(
                categoria="Erro", fonte="valor_carteira", chave_etl="X", coluna=1
            ),
            ItemMapeamento(
                categoria="OK", fonte="fixo", valor_fixo=999
            ),
        ]
        resultado = engine.resolver(carteira_mock, itens)
        assert resultado[0] == {"Categoria": "Erro", "Valor": 0.0}
        assert resultado[1] == {"Categoria": "OK", "Valor": 999}


# ===========================================================================
# Testes do ConfigDrivenBuilder
# ===========================================================================


class TestConfigDrivenBuilder:
    def test_de_dict_valido(self):
        dados = {
            "versao": "1.0",
            "fundo": "TESTE",
            "administradora": "BRL",
            "mapeamento_cd": [
                {"categoria": "Data-Base", "fonte": "atributo", "campo": "data"}
            ],
            "mapeamento_mec": [
                {"categoria": "DATA", "fonte": "atributo", "campo": "data"}
            ],
        }
        builder = ConfigDrivenBuilder.de_dict(dados)
        assert builder.fundo == "TESTE"
        assert builder.administradora == "BRL"

    def test_de_arquivo_inexistente(self):
        with pytest.raises(FileNotFoundError, match="não encontrado"):
            ConfigDrivenBuilder.de_arquivo("FUNDO_INEXISTENTE.json")

    def test_construir_mapeamento_cd(self, carteira_mock):
        dados = {
            "fundo": "TESTE",
            "administradora": "BRL",
            "mapeamento_cd": [
                {"categoria": "Data-Base", "fonte": "atributo", "campo": "data"},
                {"categoria": "PL", "fonte": "atributo", "campo": "patrimonio_total"},
            ],
            "mapeamento_mec": [],
        }
        builder = ConfigDrivenBuilder.de_dict(dados)
        resultado = builder.construir_mapeamento_cd(carteira_mock)
        assert len(resultado) == 2
        assert resultado[1]["Valor"] == 1_500_000.0

    def test_registrar_custom_fluent(self, carteira_mock):
        def minha_funcao(carteira, item):
            return 77.0

        dados = {
            "fundo": "TESTE",
            "administradora": "BRL",
            "mapeamento_cd": [
                {
                    "categoria": "Custom",
                    "fonte": "custom",
                    "nome_funcao": "minha_funcao",
                }
            ],
            "mapeamento_mec": [],
        }
        builder = (
            ConfigDrivenBuilder.de_dict(dados)
            .registrar_custom("minha_funcao", minha_funcao)
        )
        resultado = builder.construir_mapeamento_cd(carteira_mock)
        assert resultado[0]["Valor"] == 77.0

    def test_repr(self):
        dados = {
            "fundo": "ZULU",
            "administradora": "BRL",
            "mapeamento_cd": [
                {"categoria": "Data-Base", "fonte": "atributo", "campo": "data"}
            ],
            "mapeamento_mec": [],
        }
        builder = ConfigDrivenBuilder.de_dict(dados)
        assert "ZULU" in repr(builder)
        assert "BRL" in repr(builder)


# ===========================================================================
# Testes de validação de Schema Pydantic
# ===========================================================================


class TestSchemaItemMapeamento:
    def test_atributo_requer_campo(self):
        with pytest.raises(Exception, match="campo"):
            ItemMapeamento(categoria="X", fonte="atributo")

    def test_valor_carteira_requer_chave_e_coluna(self):
        with pytest.raises(Exception):
            ItemMapeamento(categoria="X", fonte="valor_carteira", chave_etl="Y")

    def test_cotas_requer_ordens_e_coluna_valor(self):
        with pytest.raises(Exception):
            ItemMapeamento(categoria="X", fonte="cotas", ordens=[99])

    def test_contas_requer_filtro(self):
        with pytest.raises(Exception, match="filtro"):
            ItemMapeamento(categoria="X", fonte="contas")

    def test_fixo_requer_valor_fixo(self):
        with pytest.raises(Exception, match="valor_fixo"):
            ItemMapeamento(categoria="X", fonte="fixo")

    def test_custom_requer_nome_funcao(self):
        with pytest.raises(Exception, match="nome_funcao"):
            ItemMapeamento(categoria="X", fonte="custom")

    def test_valido_atributo(self):
        item = ItemMapeamento(categoria="Data-Base", fonte="atributo", campo="data")
        assert item.categoria == "Data-Base"
        assert item.multiplicador == 1.0  # default


class TestSchemaMapeamentoFundo:
    def test_categorias_duplicadas_levanta_erro(self):
        dados = {
            "fundo": "X",
            "administradora": "Y",
            "mapeamento_cd": [
                {"categoria": "Data-Base", "fonte": "atributo", "campo": "data"},
                {"categoria": "Data-Base", "fonte": "atributo", "campo": "data"},
            ],
            "mapeamento_mec": [],
        }
        with pytest.raises(Exception, match="duplicadas"):
            MapeamentoFundo.model_validate(dados)

    def test_valido_completo(self):
        dados = {
            "fundo": "ZULU",
            "administradora": "BRL",
            "mapeamento_cd": [
                {"categoria": "Data-Base", "fonte": "atributo", "campo": "data"},
                {"categoria": "PL", "fonte": "atributo", "campo": "patrimonio_total"},
            ],
            "mapeamento_mec": [
                {"categoria": "DATA", "fonte": "atributo", "campo": "data"},
            ],
        }
        mf = MapeamentoFundo.model_validate(dados)
        assert mf.fundo == "ZULU"
        assert len(mf.mapeamento_cd) == 2
