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

Fundos de usuário:
    - Lidos de ``fundos_api.json`` na raiz do projeto.
    - Cadastráveis pela interface gráfica (tela Fundos).
    - Suportam múltiplos tipos de API via MAPA_APIS.

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

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from Carteira import CarteiraBase, CarteiraBRL, CarteiraAVANTI, CarteiraGenial, CarteiraTERRA, CarteiraSingulareQI
from src.core.carteira_apex_api import CarteiraApexAPI
from src.config.settings import (
    configuracoes,
    obter_contas_pagar_fundo,
    resolver_path_carteira,
    resolver_path_relatorio,
)
from src.services.excel_writer import ExcelWriter
from src.services.config_driven_builder import ConfigDrivenBuilder
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
)



# Dataclass de configuração de fundo



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
    # builder aceita:
    #   - Classe legada (ex: ZuluReportBuilder) → instanciada com builder()
    #   - Callable factory (ex: lambda: ConfigDrivenBuilder.de_arquivo("ZULU.json"))
    #     → chamada com builder() para obter a instância já configurada
    builder: type[ReportBuilderBase] | Callable[[], Any]
    chave_config_fundo: str | None = None
    abrir_apos_salvar: bool = True
    doc_fundo_api: str | None = None  # CNPJ ou identificador para consumo de API
    administrador: str | None = None
    tipo_api: str | None = None

    @property
    def chave_fundo_efetiva(self) -> str:
        """Retorna a chave de configuração de fundo com fallback para chave_gerencial."""
        return self.chave_config_fundo or self.chave_gerencial

    @property
    def administrador_efetivo(self) -> str:
        """Retorna o nome do administrador do fundo (em maiúsculo)."""
        if self.administrador:
            return self.administrador.strip().upper()
        # Fallback para as classes hardcoded
        classe_name = self.classe_carteira.__name__
        if "BRL" in classe_name:
            return "BRL"
        elif "AVANTI" in classe_name:
            return "AVANTI"
        elif "Genial" in classe_name:
            return "GENIAL"
        elif "TERRA" in classe_name:
            return "TERRA"
        elif "Singulare" in classe_name:
            return "SINGULARE"
        elif "Apex" in classe_name:
            return "APEX"
        return "OUTROS"



# Registro de fundos

# Mapa de tipos de API disponíveis → classe de carteira
# Para adicionar suporte a uma nova administradora, basta adicionar aqui.
MAPA_APIS: dict[str, type[CarteiraBase]] = {
    "apex": CarteiraApexAPI,
    # "genial": CarteiraGenialAPI,   # futuro
    # "avanti": CarteiraAvantiAPI,   # futuro
}

MAPA_CLASSES_ADMINISTRADOR: dict[str, type[CarteiraBase]] = {
    "APEX": CarteiraApexAPI,
    "AVANTI": CarteiraAVANTI,
    "GENIAL": CarteiraGenial,
    "TERRA": CarteiraTERRA,
    "SINGULARE": CarteiraSingulareQI,
}

def obter_classe_carteira(administrador: str) -> type[CarteiraBase]:
    from Carteira import Carteira
    adm_upper = administrador.strip().upper()
    for k, v in MAPA_CLASSES_ADMINISTRADOR.items():
        if k in adm_upper or adm_upper in k:
            return v
    return Carteira

# Rótulos de exibição para a interface gráfica
ROTULOS_APIS: dict[str, str] = {
    "apex": "Apex (Prisma)",
    # "genial": "Genial",
    # "avanti": "Avanti",
}

# Caminho do arquivo de fundos cadastrados pelo usuário
FUNDOS_EXTERNOS_PATH = Path(__file__).resolve().parents[1] / "fundos_api.json"

REGISTRO: dict[str, ConfiguracaoFundo] = {
    # -----------------------------------------------------------------------
    # Fundos com Administradora BRL
    # -----------------------------------------------------------------------
    # ✅ Fase 1 — Migrado para config-driven
    "FIDARA": ConfiguracaoFundo(
        nome="FIDARA FIDC",
        chave_carteira="FIDARA",
        chave_gerencial="FIDARA",
        classe_carteira=CarteiraBRL,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("FIDARA.json"),
    ),
    # ✅ Fase 1 — Migrado para config-driven
    "CDC": ConfiguracaoFundo(
        nome="CDC EMPRESTIMOS FIDC",
        chave_carteira="CDC",
        chave_gerencial="CDC",
        classe_carteira=CarteiraBRL,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("CDC.json"),
    ),
    # ✅ Fase 1 — Migrado para config-driven
    "CARMEL_II": ConfiguracaoFundo(
        nome="CARMEL II FIDC",
        chave_carteira="CARMEL_II",
        chave_gerencial="CARMEL_II",
        classe_carteira=CarteiraBRL,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("CARMEL_II.json"),
    ),
    # ✅ Fase 1 — Migrado para config-driven
    "GERAR": ConfiguracaoFundo(
        nome="GERAR CAPITAL FIDC",
        chave_carteira="GERAR",
        chave_gerencial="GERAR",
        classe_carteira=CarteiraBRL,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("GERAR.json"),
    ),
    # ✅ Fase 1 — Migrado para config-driven
    "ENEL": ConfiguracaoFundo(
        nome="ENEL II FIDC",
        chave_carteira="ENEL",
        chave_gerencial="ENEL",
        classe_carteira=CarteiraBRL,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("ENEL.json"),
    ),
    # ✅ Fase 1 — Migrado para config-driven
    "HOUSI": ConfiguracaoFundo(
        nome="HOUSI FIDC",
        chave_carteira="HOUSI",
        chave_gerencial="HOUSI",
        classe_carteira=CarteiraBRL,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("HOUSI.json"),
    ),
    # ✅ Fase 1 — Migrado para config-driven
    "INFRA": ConfiguracaoFundo(
        nome="INFRA PORTFOLIO I",
        chave_carteira="INFRA",
        chave_gerencial="INFRA",
        classe_carteira=CarteiraBRL,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("INFRA.json"),
    ),
    # ✅ Fase 1 — Migrado para config-driven
    "MOOVPAY": ConfiguracaoFundo(
        nome="MOOVPAY",
        chave_carteira="MOOVPAY",
        chave_gerencial="MOOVPAY",
        classe_carteira=CarteiraBRL,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("MOOVPAY.json"),
    ),
    # ✅ Fase 1 — Migrado para config-driven
    "RESIDENCE": ConfiguracaoFundo(
        nome="RESIDENCE CLUB FIDC",
        chave_carteira="RESIDENCE",
        chave_gerencial="RESIDENCE",
        classe_carteira=CarteiraBRL,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("RESIDENCE.json"),
    ),
    # ✅ Fase 1 — Migrado para config-driven
    "SB_II": ConfiguracaoFundo(
        nome="SB MULTIESTRATEGIA II",
        chave_carteira="SB_II",
        chave_gerencial="SB_II",
        classe_carteira=CarteiraBRL,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("SB_II.json"),
        chave_config_fundo="SB_II",
    ),
    # ✅ Fase 1 — Migrado para config-driven
    "ZULU": ConfiguracaoFundo(
        nome="ZULU FIP",
        chave_carteira="ZULU",
        chave_gerencial="ZULU",
        classe_carteira=CarteiraBRL,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("ZULU.json"),
    ),
    "VIRTUS": ConfiguracaoFundo(
        nome="VIRTUS CAPITAL",
        chave_carteira="VIRTUS",
        chave_gerencial="VIRTUS",
        classe_carteira=CarteiraBRL,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("VIRTUS.json"),
    ),
    # ✅ Fase 1 — Migrado para config-driven
    "CREDITOS_COLATERALIZADOS": ConfiguracaoFundo(
        nome="CRÉDITOS COLATERALIZADOS I",
        chave_carteira="CREDITOS_COLATERALIZADOS",
        chave_gerencial="CREDITOS_COLATERALIZADOS",
        classe_carteira=CarteiraBRL,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("CREDITOS_COLATERALIZADOS.json"),
    ),
    # ✅ Fase 1 — Migrado para config-driven
    "AVANTI": ConfiguracaoFundo(
        nome="AVANTI FIDC",
        chave_carteira="AVANTI",
        chave_gerencial="AVANTI",
        classe_carteira=CarteiraAVANTI,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("AVANTI.json"),
    ),
    # ✅ Singulare/QI — Cobuccio FIDC
    "COBUCCIO_FIDC": ConfiguracaoFundo(
        nome="COBUCCIO FIDC",
        chave_carteira="COBUCCIO FIDC",
        chave_gerencial="COBUCCIO FIDC",
        classe_carteira=CarteiraSingulareQI,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("COBUCCIO_FIDC.json"),
        chave_config_fundo="COBUCCIO FIDC",
        administrador="SINGULARE",
    ),
    # ✅ Singulare/QI — SB Credito FIDC
    "SB_CREDITO_FIDC": ConfiguracaoFundo(
        nome="SB CREDITO FIDC",
        chave_carteira="SB CREDITO FIDC",
        chave_gerencial="SB CREDITO FIDC",
        classe_carteira=CarteiraSingulareQI,
        builder=lambda: ConfigDrivenBuilder.de_arquivo("SB_CREDITO_FIDC.json"),
        chave_config_fundo="SB CREDITO FIDC",
        administrador="SINGULARE",
    ),
}

# ---------------------------------------------------------------------------
# Gestão de fundos externos (cadastrados pelo usuário via interface)
# ---------------------------------------------------------------------------

def _criar_mapeamento_vazio(chave: str) -> None:
    """Cria um arquivo de mapeamento vazio para um fundo novo se ainda não existir."""
    from pathlib import Path
    mapeamentos_dir = Path(__file__).resolve().parents[1] / "mapeamentos"
    path = mapeamentos_dir / f"{chave}.json"
    if not path.exists():
        vazio = {
            "versao": "1.0",
            "fundo": chave,
            "administradora": "API",
            "mapeamento_cd": [],
            "mapeamento_mec": []
        }
        path.write_text(json.dumps(vazio, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Mapeamento vazio criado: {path}")

def gerar_mapeamento_padrao(chave: str, chave_gerencial: str = "") -> None:
    """
    Tenta ler as colunas reais do arquivo Excel do fundo (CD_ATUAL e MEC)
    a partir da 'Data-Base' (CD) e 'DATA' (MEC).
    Se falhar ou não houver chave gerencial, cai de volta nas colunas padrão hardcoded.
    """
    from pathlib import Path
    import json
    import pandas as pd
    
    mapeamentos_dir = Path(__file__).resolve().parents[1] / "mapeamentos"
    path = mapeamentos_dir / f"{chave}.json"
    
    # 1. Definição do fallback (padrão)
    padrao_cd = [
        {"categoria": "Data-Base", "fonte": "atributo", "campo": "data"},
        {"categoria": "Direitos Creditórios a Vencer", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Direitos Creditórios Vencidos", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "PDD - Prov. de Perdas", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Saldo em Tesouraria", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Taxa de Administração", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Taxa Consultoria", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Taxa de Custódia", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Taxa de Gestão", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Taxa de Auditoria", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Taxa ANBIMA", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Taxa Fisc. CVM", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Taxa de Performance", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Outras despesas  (-)", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Dif. de despesa CVM", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Dif. de despesa ANBIMA", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Outros valores a receber  (+)", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Ajuste de Compensação de Cotas", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Senior (-)", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Mezanino (-)", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Títulos Públicos", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "PL Carteira Subordinada Digitar", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "Subordinação Mínima", "fonte": "fixo", "valor_fixo": 0.0}
    ]
    
    padrao_mec = [
        {"categoria": "DATA", "fonte": "atributo", "campo": "data"},
        {"categoria": "VALOR DE APLICAÇÃO SUBORDINADA", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "COTAS EMITIDAS SUBORDINADA", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "VALOR DE RESGATE SUBORDINADA", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "QUANT COTAS SUBORDINADA", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "VALOR DA COTA SUBORDINADA", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "AMORTIZ. DIA SUBORDINADA", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "VALOR DE APLICAÇÃO SENIOR", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "COTAS EMITIDAS SENIOR", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "VALOR DE RESGATE SENIOR", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "COTAS RESGATADAS SENIOR", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "QUANT COTAS SENIOR", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "VALOR DA COTA - SENIOR", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "AMORTIZ. DIA SENIOR", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "VALOR DE APLICAÇÃO MEZANINO", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "COTAS EMITIDAS MEZANINO", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "VALOR DE RESGATE MEZANINO", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "COTAS RESGATADAS MEZANINO", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "QUANT COTAS MEZANINO", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "VALOR DA COTA - MEZANINO", "fonte": "fixo", "valor_fixo": 0.0},
        {"categoria": "AMORTIZ. DIA MEZANINO", "fonte": "fixo", "valor_fixo": 0.0}
    ]

    mapeamento_cd = padrao_cd
    mapeamento_mec = padrao_mec
    excel_lido_sucesso = False

    # 2. Tenta ler o arquivo Excel dinamicamente se chave_gerencial for informada
    if chave_gerencial:
        try:
            from src.config.settings import resolver_path_relatorio
            excel_path = resolver_path_relatorio(chave_gerencial)
            
            if excel_path and Path(excel_path).exists():
                logger.info(f"Tentando ler colunas do Excel: {excel_path}")
                
                # Helper interno para extrair colunas de uma aba
                def _extrair_colunas(sheet_name: str, anchor: str) -> list[str]:
                    # Match case-insensitive para abas
                    xls = pd.ExcelFile(excel_path)
                    matched_sheet = None
                    for s in xls.sheet_names:
                        if s.strip().upper() == sheet_name.upper():
                            matched_sheet = s
                            break
                    if not matched_sheet:
                        raise ValueError(f"Aba '{sheet_name}' não encontrada.")
                    
                    df = pd.read_excel(excel_path, sheet_name=matched_sheet, header=None)
                    
                    found_row = None
                    found_col = None
                    for r in range(len(df)):
                        for c in range(df.shape[1]):
                            val = df.iloc[r, c]
                            if isinstance(val, str) and val.strip().lower() == anchor.strip().lower():
                                found_row = r
                                found_col = c
                                break
                        if found_row is not None:
                            break
                            
                    if found_row is None:
                        raise ValueError(f"Âncora '{anchor}' não encontrada.")
                        
                    cols = []
                    for c in range(found_col, df.shape[1]):
                        val = df.iloc[found_row, c]
                        if pd.isna(val) or val is None:
                            break
                        val_str = str(val).strip()
                        if not val_str:
                            break
                        cols.append(val_str)
                    return cols

                # Tenta extrair colunas da aba CD_ATUAL
                try:
                    cols_cd = _extrair_colunas("CD_ATUAL", "Data-Base")
                    if cols_cd:
                        mapeamento_cd = []
                        for col in cols_cd:
                            if col.lower() == "data-base":
                                mapeamento_cd.append({"categoria": col, "fonte": "atributo", "campo": "data"})
                            else:
                                mapeamento_cd.append({"categoria": col, "fonte": "fixo", "valor_fixo": 0.0})
                        logger.info(f"CD_ATUAL mapeado dinamicamente com {len(cols_cd)} colunas.")
                except Exception as e_cd:
                    logger.warning(f"Falha ao ler CD_ATUAL do Excel ({e_cd}). Usando padrão.")
                    
                # Tenta extrair colunas da aba MEC
                try:
                    cols_mec = _extrair_colunas("MEC", "DATA")
                    if cols_mec:
                        mapeamento_mec = []
                        for col in cols_mec:
                            if col.lower() == "data":
                                mapeamento_mec.append({"categoria": col, "fonte": "atributo", "campo": "data"})
                            else:
                                mapeamento_mec.append({"categoria": col, "fonte": "fixo", "valor_fixo": 0.0})
                        logger.info(f"MEC mapeado dinamicamente com {len(cols_mec)} colunas.")
                except Exception as e_mec:
                    logger.warning(f"Falha ao ler MEC do Excel ({e_mec}). Usando padrão.")
                    
                excel_lido_sucesso = True
            else:
                logger.warning(f"Arquivo Excel para a chave gerencial '{chave_gerencial}' não foi encontrado em: {excel_path}")
        except Exception as exc:
            logger.warning(f"Erro ao processar mapeamento dinâmico via Excel: {exc}")

    # 3. Escreve o JSON final
    padrao = {
        "versao": "1.0",
        "fundo": chave,
        "administradora": "API",
        "mapeamento_cd": mapeamento_cd,
        "mapeamento_mec": mapeamento_mec
    }
    
    path.write_text(json.dumps(padrao, ensure_ascii=False, indent=2), encoding="utf-8")
    
    if excel_lido_sucesso:
        logger.info(f"Mapeamento dinâmico gerado com sucesso para: {chave}")
    else:
        logger.info(f"Mapeamento padrão (fallback) gerado com sucesso para: {chave}")


def carregar_fundos_externos() -> None:
    """
    Lê fundos_api.json e mescla as entradas no REGISTRO em tempo de execução.

    Fundos externos usam:
        - A classe de carteira definida em MAPA_APIS pelo campo tipo_api.
        - O ConfigDrivenBuilder com o arquivo mapeamentos/{chave}.json.
        - O chave_gerencial para localizar o arquivo Excel de destino.
    """
    if not FUNDOS_EXTERNOS_PATH.exists():
        return
    try:
        dados = json.loads(FUNDOS_EXTERNOS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Não foi possível carregar fundos_api.json: {exc}")
        return

    for entry in dados:
        chave = entry.get("chave", "").upper().strip()
        if not chave or chave in REGISTRO:
            continue

        administrador = entry.get("administrador", "APEX")
        tipo_api = entry.get("tipo_api", "apex").lower()
        classe_carteira = obter_classe_carteira(administrador)
        arquivo_mapeamento = f"{chave}.json"

        # Garante que o arquivo de mapeamento existe
        _criar_mapeamento_vazio(chave)

        REGISTRO[chave] = ConfiguracaoFundo(
            nome=entry.get("nome", chave),
            chave_carteira=entry.get("chave_gerencial", chave),
            chave_gerencial=entry.get("chave_gerencial", chave),
            classe_carteira=classe_carteira,
            builder=lambda _f=arquivo_mapeamento: ConfigDrivenBuilder.de_arquivo(_f),
            chave_config_fundo=entry.get("chave_gerencial", chave),
            doc_fundo_api=entry.get("doc_fundo_api", ""),
            administrador=administrador,
            tipo_api=tipo_api,
        )
        logger.info(f"Fundo externo carregado: {chave} ({tipo_api})")


def listar_fundos_externos() -> list[dict]:
    """Retorna a lista de fundos cadastrados pelo usuário no fundos_api.json."""
    if not FUNDOS_EXTERNOS_PATH.exists():
        return []
    try:
        return json.loads(FUNDOS_EXTERNOS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def salvar_fundo_externo(entry: dict) -> None:
    """
    Salva ou atualiza um fundo no fundos_api.json.
    Campos obrigatórios: chave, nome, tipo_api, doc_fundo_api, chave_gerencial.
    """
    dados = listar_fundos_externos()
    chave = entry["chave"].upper().strip()
    entry["chave"] = chave

    # Substitui se já existe, senão adiciona
    idx = next((i for i, d in enumerate(dados) if d.get("chave") == chave), None)
    if idx is not None:
        dados[idx] = entry
    else:
        dados.append(entry)

    FUNDOS_EXTERNOS_PATH.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    _criar_mapeamento_vazio(chave)

    # Atualiza o REGISTRO em memória imediatamente
    administrador = entry.get("administrador", "APEX")
    tipo_api = entry.get("tipo_api", "apex").lower()
    classe_carteira = obter_classe_carteira(administrador)
    arquivo_mapeamento = f"{chave}.json"
    REGISTRO[chave] = ConfiguracaoFundo(
        nome=entry.get("nome", chave),
        chave_carteira=entry.get("chave_gerencial", chave),
        chave_gerencial=entry.get("chave_gerencial", chave),
        classe_carteira=classe_carteira,
        builder=lambda _f=arquivo_mapeamento: ConfigDrivenBuilder.de_arquivo(_f),
        chave_config_fundo=entry.get("chave_gerencial", chave),
        doc_fundo_api=entry.get("doc_fundo_api", ""),
        administrador=administrador,
        tipo_api=tipo_api,
    )


def remover_fundo_externo(chave: str) -> None:
    """Remove um fundo do fundos_api.json e do REGISTRO em memória."""
    chave = chave.upper().strip()
    dados = listar_fundos_externos()
    dados = [d for d in dados if d.get("chave") != chave]
    FUNDOS_EXTERNOS_PATH.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    REGISTRO.pop(chave, None)


def obter_fundos_api() -> list[str]:
    """Retorna a lista de chaves dos fundos que suportam ingestão via API."""
    return [
        chave for chave, cfg in REGISTRO.items()
        if getattr(cfg, "doc_fundo_api", None) and getattr(cfg, "administrador", "APEX").upper() == "APEX"
    ]


# Carrega fundos externos automaticamente ao importar o módulo
carregar_fundos_externos()

# Executor genérico

def processar_fundo_registrado(
    nome_fundo: str,
    aba: str = "CD_ATUAL",
    writer: ExcelWriter | None = None,
    data_referencia: Any | None = None,
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

    start_total = time.time()
    
    # Resolve caminhos
    path_carteira = resolver_path_carteira(cfg.chave_carteira)
    path_relatorio = resolver_path_relatorio(cfg.chave_gerencial)

    logger.info(f"\n>>> Processando: {cfg.nome} (aba: {aba})")

    # Instancia e configura a carteira
    start_ingestion = time.time()
    if getattr(cfg, "doc_fundo_api", None) and hasattr(cfg.classe_carteira, "criar_da_api"):
        from datetime import date, timedelta
        data_ref = data_referencia if data_referencia is not None else date.today() - timedelta(days=1)
        carteira = cfg.classe_carteira.criar_da_api(cfg.doc_fundo_api, data_ref)
        contas_pagar = obter_contas_pagar_fundo(cfg.chave_fundo_efetiva)
        if contas_pagar:
            carteira.acrescentar_contas_pagar(*contas_pagar)
    else:
        carteira = cfg.classe_carteira(path_carteira)
        contas_pagar = obter_contas_pagar_fundo(cfg.chave_fundo_efetiva)
        if contas_pagar:
            carteira.acrescentar_contas_pagar(*contas_pagar)
        carteira.carregar_dados(aba=aba)
    
    ingestion_time = time.time() - start_ingestion
    logger.info(f"Ingestão concluída em {ingestion_time:.2f}s")

    # Constrói os mapeamentos
    start_mapping = time.time()
    builder = cfg.builder()
    mapeamento_cd = builder.construir_mapeamento_cd(carteira)
    mapeamento_mec = builder.construir_mapeamento_mec(carteira)

    # Persiste
    excel_writer = writer or ExcelWriter()
    excel_writer.salvar_carteira_diaria(path_relatorio, mapeamento_cd, mapeamento_mec)
    
    mapping_time = time.time() - start_mapping
    total_time = time.time() - start_total
    
    logger.info(f"Mapeamento/Excel concluído em {mapping_time:.2f}s")
    logger.info(f"✔ {cfg.nome} processado com sucesso em {total_time:.2f}s.")

    # Abre o relatório se configurado
    if cfg.abrir_apos_salvar:
        os.startfile(path_relatorio)

    return getattr(carteira, "warnings", [])



def listar_fundos_registrados() -> list[str]:
    """Retorna a lista de fundos disponíveis no registro.

    Returns:
        list[str]: Chaves dos fundos cadastrados no REGISTRO.
    """
    return list(REGISTRO.keys())
