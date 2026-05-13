"""
Registro central de fundos — substitui o MAPA_FUNCOES manual.

Em vez de criar uma função ``gerar_carteira_X()`` para cada fundo,
o sistema declara os fundos aqui como configuração pura.
O executor em ``carteira_apex.py`` consulta este registro para saber
qual classe de carteira e qual builder usar para cada fundo.

Design (Open/Closed Principle):
    - Para adicionar um novo fundo: adicione uma entrada ao ``REGISTRO``.
    - Nenhuma função existente precisa ser alterada.
    - Builders e classes de carteira são injetados — testáveis com mocks.

Migração futura:
    - Este registro pode ser carregado de banco de dados ou arquivo YAML
      sem alterar o executor — apenas a fonte do registro muda.

Uso:
    from src.registry import REGISTRO, processar_fundo_registrado

    processar_fundo_registrado("FIDARA", aba="CD_ATUAL")
"""

from __future__ import annotations
from src.core.logger import get_logger
logger = get_logger(__name__)

import os
from dataclasses import dataclass, field
from typing import Any

from Carteira import CarteiraBase, CarteiraBRL, CarteiraAVANTI
from src.config.settings import (
    configuracoes,
    obter_contas_pagar_fundo,
    resolver_path_carteira,
    resolver_path_relatorio,
)
from src.services.excel_writer import ExcelWriter
from src.services.report_builder import (
    AvantiReportBuilder,
    CarmelIIReportBuilder,
    CdcReportBuilder,
    CreditosColateralizadosReportBuilder,
    EnelReportBuilder,
    FidaraReportBuilder,
    GerarReportBuilder,
    HousiReportBuilder,
    InfraReportBuilder,
    MoovpayReportBuilder,
    ReportBuilderBase,
    ResidenceReportBuilder,
    SbIIReportBuilder,
    VirtusReportBuilder,
    ZuluReportBuilder,
)


# ---------------------------------------------------------------------------
# Dataclass de configuração de fundo
# ---------------------------------------------------------------------------


@dataclass
class ConfiguracaoFundo:
    """Configuração declarativa completa de um fundo.

    Attributes:
        nome: Nome de exibição do fundo.
        chave_carteira: Chave em config.json['carteiras'].
        chave_gerencial: Chave em config.json['arquivo_gerencial'].
        classe_carteira: Classe Python a instanciar (ex: CarteiraBRL).
        builder: Classe do builder de relatório.
        chave_config_fundo: Chave em config.json['configuracoes_fundos'].
            Se None, usa o mesmo valor de ``chave_gerencial``.
        abrir_apos_salvar: Se True, abre o arquivo após salvar.
    """

    nome: str
    chave_carteira: str
    chave_gerencial: str
    classe_carteira: type[CarteiraBase]
    builder: type[ReportBuilderBase]
    chave_config_fundo: str | None = None
    abrir_apos_salvar: bool = True

    @property
    def chave_fundo_efetiva(self) -> str:
        """Retorna a chave de configuração de fundo com fallback para chave_gerencial."""
        return self.chave_config_fundo or self.chave_gerencial


# ---------------------------------------------------------------------------
# Registro de fundos
# ---------------------------------------------------------------------------

REGISTRO: dict[str, ConfiguracaoFundo] = {
    # -----------------------------------------------------------------------
    # Fundos com Administradora BRL
    # -----------------------------------------------------------------------
    "FIDARA": ConfiguracaoFundo(
        nome="FIDARA FIDC",
        chave_carteira="FIDARA",
        chave_gerencial="FIDARA",
        classe_carteira=CarteiraBRL,
        builder=FidaraReportBuilder,
    ),
    "CDC": ConfiguracaoFundo(
        nome="CDC EMPRESTIMOS FIDC",
        chave_carteira="CDC",
        chave_gerencial="CDC",
        classe_carteira=CarteiraBRL,
        builder=CdcReportBuilder,
    ),
    "CARMEL_II": ConfiguracaoFundo(
        nome="CARMEL II FIDC",
        chave_carteira="CARMEL_II",
        chave_gerencial="CARMEL_II",
        classe_carteira=CarteiraBRL,
        builder=CarmelIIReportBuilder,
    ),
    "GERAR": ConfiguracaoFundo(
        nome="GERAR CAPITAL FIDC",
        chave_carteira="GERAR",
        chave_gerencial="GERAR",
        classe_carteira=CarteiraBRL,
        builder=GerarReportBuilder,
    ),
    "ENEL": ConfiguracaoFundo(
        nome="ENEL II FIDC",
        chave_carteira="ENEL",
        chave_gerencial="ENEL",
        classe_carteira=CarteiraBRL,
        builder=EnelReportBuilder,
    ),
    "HOUSI": ConfiguracaoFundo(
        nome="HOUSI FIDC",
        chave_carteira="HOUSI",
        chave_gerencial="HOUSI",
        classe_carteira=CarteiraBRL,
        builder=HousiReportBuilder,
    ),
    "INFRA": ConfiguracaoFundo(
        nome="INFRA PORTFOLIO I",
        chave_carteira="INFRA",
        chave_gerencial="INFRA",
        classe_carteira=CarteiraBRL,
        builder=InfraReportBuilder,
    ),
    "MOOVPAY": ConfiguracaoFundo(
        nome="MOOVPAY",
        chave_carteira="MOOVPAY",
        chave_gerencial="MOOVPAY",
        classe_carteira=CarteiraBRL,
        builder=MoovpayReportBuilder,
    ),
    "RESIDENCE": ConfiguracaoFundo(
        nome="RESIDENCE CLUB FIDC",
        chave_carteira="RESIDENCE",
        chave_gerencial="RESIDENCE",
        classe_carteira=CarteiraBRL,
        builder=ResidenceReportBuilder,
    ),
    "SB_II": ConfiguracaoFundo(
        nome="SB MULTIESTRATEGIA II",
        chave_carteira="SB II",
        chave_gerencial="SB II",
        classe_carteira=CarteiraBRL,
        builder=SbIIReportBuilder,
        chave_config_fundo="SB II",
    ),
    "ZULU": ConfiguracaoFundo(
        nome="ZULU FIP",
        chave_carteira="ZULU",
        chave_gerencial="ZULU",
        classe_carteira=CarteiraBRL,
        builder=ZuluReportBuilder,
    ),
    "VIRTUS": ConfiguracaoFundo(
        nome="VIRTUS CAPITAL",
        chave_carteira="VIRTUS",
        chave_gerencial="VIRTUS",
        classe_carteira=CarteiraBRL,
        builder=VirtusReportBuilder,
    ),
    "CREDITOS_COLATERALIZADOS": ConfiguracaoFundo(
        nome="CRÉDITOS COLATERALIZADOS I",
        chave_carteira="CREDITOS_COLATERALIZADOS",
        chave_gerencial="CREDITOS_COLATERALIZADOS",
        classe_carteira=CarteiraBRL,
        builder=CreditosColateralizadosReportBuilder,
    ),
    "AVANTI": ConfiguracaoFundo(
        nome="AVANTI FIDC",
        chave_carteira="AVANTI",
        chave_gerencial="AVANTI",
        classe_carteira=CarteiraAVANTI,
        builder=AvantiReportBuilder,
    ),
}


# ---------------------------------------------------------------------------
# Executor genérico
# ---------------------------------------------------------------------------


def processar_fundo_registrado(
    nome_fundo: str,
    aba: str = "CD_ATUAL",
    writer: ExcelWriter | None = None,
) -> None:
    """Processa um fundo consultando o registro centralizado.

    Este é o ponto de entrada único para processar qualquer fundo.
    Elimina a necessidade de funções ``gerar_carteira_X()`` individuais.

    Fluxo:
        1. Consulta o REGISTRO pelo nome do fundo.
        2. Resolve os caminhos (carteira e relatório) via settings.
        3. Instancia a classe de carteira correta.
        4. Configura as contas a pagar conforme config.json.
        5. Carrega os dados da carteira.
        6. Constrói os mapeamentos CD/MEC via builder.
        7. Persiste os dados via ExcelWriter.
        8. Abre o arquivo de relatório (opcional).

    Args:
        nome_fundo: Chave do fundo no REGISTRO (ex: "FIDARA", "CDC").
        aba: Nome da aba Excel a processar. Padrão: "CD_ATUAL".
        writer: Instância de ExcelWriter (injeção de dependência — facilita
            mocking em testes). Se None, cria uma instância padrão.

    Raises:
        KeyError: Se o fundo não estiver cadastrado no REGISTRO.
        RuntimeError: Em caso de falha no carregamento ou na persistência.

    Example:
        >>> processar_fundo_registrado("FIDARA")
        >>> processar_fundo_registrado("CDC", aba="CD_ATUAL")
    """
    nome_fundo = nome_fundo.upper().strip()

    if nome_fundo not in REGISTRO:
        fundos_disponiveis = list(REGISTRO.keys())
        raise KeyError(
            f"Fundo '{nome_fundo}' não encontrado no registro.\n"
            f"Fundos disponíveis: {fundos_disponiveis}"
        )

    cfg = REGISTRO[nome_fundo]

    logger.info(f"\n>>> Processando: {cfg.nome} (aba: {aba})")
    
    import time
    start_time = time.time()

    # Resolve paths
    path_carteira = resolver_path_carteira(cfg.chave_carteira)
    path_relatorio = resolver_path_relatorio(cfg.chave_gerencial)

    # Instancia e configura a carteira
    carteira = cfg.classe_carteira(path_carteira)
    contas_pagar = obter_contas_pagar_fundo(cfg.chave_fundo_efetiva)
    if contas_pagar:
        carteira.acrescentar_contas_pagar(*contas_pagar)

    # Carrega os dados
    carteira.carregar_dados(aba=aba)

    # Constrói os mapeamentos
    builder = cfg.builder()
    mapeamento_cd = builder.construir_mapeamento_cd(carteira)
    mapeamento_mec = builder.construir_mapeamento_mec(carteira)

    # Persiste
    excel_writer = writer or ExcelWriter()
    excel_writer.salvar_carteira_diaria(path_relatorio, mapeamento_cd, mapeamento_mec)

    # Abre o relatório se configurado
    if cfg.abrir_apos_salvar:
        os.startfile(path_relatorio)

    elapsed_time = time.time() - start_time
    logger.info(f"✔ {cfg.nome} processado com sucesso em {elapsed_time:.2f}s.")


def listar_fundos_registrados() -> list[str]:
    """Retorna a lista de fundos disponíveis no registro.

    Returns:
        list[str]: Chaves dos fundos cadastrados no REGISTRO.
    """
    return list(REGISTRO.keys())
