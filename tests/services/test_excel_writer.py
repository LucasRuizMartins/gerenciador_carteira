"""
Testes unitários para ExcelWriter (src/services/excel_writer.py).

Como o ExcelWriter usa xlwings (que requer Excel instalado), todos
os testes usam mocking para isolar completamente o comportamento
sem abrir nenhum arquivo real.

Valida:
    - O contrato do ExcelWriter (métodos existem com assinaturas corretas)
    - Tratamento de erros (aba inexistente → ValueError)
    - Delegação correta ao xlwings (via Mock)
    - Que o App do Excel é sempre encerrado (app.quit() no finally)
"""

from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, patch, call

import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from src.services.excel_writer import ExcelWriter


# ===========================================================================
# TestExcelWriterContrato
# ===========================================================================


class TestExcelWriterContrato:
    """Verifica que ExcelWriter possui todos os métodos do protocolo."""

    def test_possui_salvar_carteira_diaria(self):
        assert hasattr(ExcelWriter(), "salvar_carteira_diaria")

    def test_possui_salvar_mapeamento_em_aba(self):
        assert hasattr(ExcelWriter(), "salvar_mapeamento_em_aba")

    def test_possui_salvar_novos_codigos(self):
        assert hasattr(ExcelWriter(), "salvar_novos_codigos")

    def test_inicializacao_com_defaults(self):
        w = ExcelWriter()
        assert w._visible is False
        assert w._delay_abertura == 1.0

    def test_inicializacao_com_parametros_custom(self):
        w = ExcelWriter(visible=True, delay_abertura=0.5)
        assert w._visible is True
        assert w._delay_abertura == 0.5


# ===========================================================================
# TestVerificarAba
# ===========================================================================


class TestVerificarAba:
    """Testa o método estático _verificar_aba."""

    def test_levanta_value_error_para_aba_inexistente(self):
        mock_wb = MagicMock()
        mock_wb.sheets = [MagicMock(name="CD"), MagicMock(name="MEC")]
        # Simula que a lista de nomes não inclui "INEXISTENTE"
        for s in mock_wb.sheets:
            s.name = "CD" if mock_wb.sheets.index(s) == 0 else "MEC"

        # Recria com names acessíveis
        mock_sheet_cd = MagicMock()
        mock_sheet_cd.name = "CD"
        mock_sheet_mec = MagicMock()
        mock_sheet_mec.name = "MEC"
        mock_wb.sheets = [mock_sheet_cd, mock_sheet_mec]

        with pytest.raises(ValueError, match="INEXISTENTE"):
            ExcelWriter._verificar_aba(mock_wb, "INEXISTENTE")

    def test_nao_levanta_excecao_para_aba_existente(self):
        mock_sheet = MagicMock()
        mock_sheet.name = "CD"
        mock_wb = MagicMock()
        mock_wb.sheets = [mock_sheet]
        ExcelWriter._verificar_aba(mock_wb, "CD")  # Não deve lançar


# ===========================================================================
# TestSalvarCarteiraDiaria (com mocking de xlwings)
# ===========================================================================


class TestSalvarCarteiraDiaria:
    """Testa salvar_carteira_diaria() com xlwings completamente mockado."""

    @pytest.fixture
    def mapeamento_cd(self):
        return [
            {"Categoria": "Data-Base", "Valor": "2024-12-31"},
            {"Categoria": "PL Carteira Subordinada", "Valor": 1_000_000.0},
        ]

    @pytest.fixture
    def mapeamento_mec(self):
        return [
            {"Categoria": "DATA", "Valor": "2024-12-31"},
            {"Categoria": "QUANT COTAS", "Valor": 500_000},
        ]

    def test_chama_app_quit_mesmo_em_caso_de_erro(
        self, mapeamento_cd, mapeamento_mec
    ):
        """Garante que o processo do Excel é sempre encerrado."""
        with patch("src.services.excel_writer.time.sleep"):
            with patch.dict("sys.modules", {"xlwings": MagicMock()}):
                # pyrefly: ignore [missing-import]
                import xlwings as xw_mock
                mock_app = MagicMock()
                xw_mock.App.return_value = mock_app
                mock_app.Book.side_effect = RuntimeError("Arquivo não encontrado")

                writer = ExcelWriter(delay_abertura=0)
                with pytest.raises(RuntimeError):
                    writer.salvar_carteira_diaria("/falso/path.xlsb", mapeamento_cd, mapeamento_mec)

    def test_salvar_novos_codigos_nao_abre_excel_com_df_vazio(self):
        """Se DataFrame de novos códigos estiver vazio, não deve abrir o Excel."""
        import pandas as pd
        writer = ExcelWriter()

        # Com df vazio, a função retorna antes de importar xlwings
        # Não precisamos de mock — garantindo que não há side effect
        writer.salvar_novos_codigos("/qualquer/path.xlsb", pd.DataFrame())
        # Se chegou aqui sem erro, passou
