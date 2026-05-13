from __future__ import annotations

import sys
import os
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# Garante que o diretório raiz do projeto está no sys.path
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from Carteira import CarteiraBRL
from src.registry import processar_fundo_registrado, REGISTRO, ConfiguracaoFundo
from src.services.report_builder import FidaraReportBuilder
from src.services.excel_writer import PersistenciaBackend

class MockExcelWriter(PersistenciaBackend):
    def salvar_carteira_diaria(self, path: str, mapeamento_excel_cd: list[dict], mapeamento_excel_mec: list[dict]) -> None:
        self.path = path
        self.mapeamento_cd = mapeamento_excel_cd
        self.mapeamento_mec = mapeamento_excel_mec

@pytest.fixture
def df_sintetico():
    return pd.DataFrame({
        "Unnamed: 0": [
            "Data Posição",
            "HEADER_BOGUS",
            "SÉRIES DE EMISSÃO",
            "SENIOR",
            "MEZANINO",
            "SUBORDINADA",
            "VALORES A PAGAR",
            "Taxa de Administração",
            "SALDO TOTAL",
            "PATRIMÔNIO LIQUIDO",
        ],
        "Unnamed: 1": [
            "01/10/2023",
            "VALOR_BOGUS",
            None,
            "1000.0",
            "500.0",
            "300.0",
            None,
            "-50.0",
            "10000.0",
            "100000.0",
        ]
    })

def test_pipeline_integracao_completa(df_sintetico, tmp_path):
    # Simula a leitura do Excel para retornar nosso DF sintético
    with patch("pandas.read_excel") as mock_read_excel:
        mock_read_excel.return_value = df_sintetico
        
        # Cria um arquivo temp fake para a carteira e o relatório
        fake_path = tmp_path / "fake_carteira.xlsx"
        fake_path.touch()
        
        # Injeta um config temporário no REGISTRO
        REGISTRO["TESTE_SINTETICO"] = ConfiguracaoFundo(
            nome="TESTE_SINTETICO",
            chave_carteira="fake",
            chave_gerencial="fake",
            chave_config_fundo="TESTE",
            classe_carteira=CarteiraBRL,
            builder=FidaraReportBuilder,
            abrir_apos_salvar=False
        )
        
        mock_writer = MockExcelWriter()
        
        # Para que o resolver path não quebre
        with patch("src.registry.resolver_path_carteira", return_value=str(fake_path)):
            with patch("src.registry.resolver_path_relatorio", return_value="out.xlsx"):
                with patch("src.registry.obter_contas_pagar_fundo", return_value=[]):
                    processar_fundo_registrado("TESTE_SINTETICO", aba="CD_ATUAL", writer=mock_writer)
                    
        # Verificamos se o writer foi chamado
        assert getattr(mock_writer, "mapeamento_cd", None) is not None
        assert getattr(mock_writer, "mapeamento_mec", None) is not None
        assert len(mock_writer.mapeamento_cd) > 0
        
        # Remove do registro para não sujar o ambiente
        del REGISTRO["TESTE_SINTETICO"]
