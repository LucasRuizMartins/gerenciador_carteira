"""
Módulo de configuração centralizada do sistema de carteiras.

Responsabilidade única: carregar, cachear e expor as configurações
definidas em config.json, resolvendo caminhos de forma dinâmica
e independente do usuário do sistema operacional.

Design para extensibilidade:
    - Hoje: leitura de config.json + paths do sistema de arquivos
    - Futuro: pode ser substituído por variáveis de ambiente, banco de dados,
      ou serviço de configuração sem alterar os consumidores.

Uso:
    from src.config.settings import configuracoes, resolver_path

    cfg = configuracoes()
    path = resolver_path(cfg["carteiras"]["FIDARA"])
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Carregamento de Ambiente
# ---------------------------------------------------------------------------

# Resolve sempre relativo à raiz do projeto (dois níveis acima de src/config/)
RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent
load_dotenv(RAIZ_PROJETO / ".env")


# ---------------------------------------------------------------------------
# Schemas de Validação (Pydantic)
# ---------------------------------------------------------------------------

class PathsConfig(BaseModel):
    root_dir: str = Field(default_factory=lambda: os.getenv("ROOT_DIR", ""))
    relatorio_diario: str
    estoque: str
    feriados: str

class FundoConfigItem(BaseModel):
    contas_pagar: list[str]

class AppSettings(BaseModel):
    """Schema completo do config.json validado pelo Pydantic."""
    paths: PathsConfig
    arquivo_gerencial: dict[str, str]
    laminas: dict[str, str]
    carteiras: dict[str, str]
    configuracoes_fundos: dict[str, FundoConfigItem]
    destinatarios: list[str]

    @field_validator("paths")
    @classmethod
    def validar_root_dir(cls, v: PathsConfig) -> PathsConfig:
        if not v.root_dir:
            v.root_dir = os.getenv("ROOT_DIR", "")
        if not v.root_dir:
            raise ValueError("ROOT_DIR deve estar definido no .env ou no config.json")
        return v


# ---------------------------------------------------------------------------
# Carregamento e cache
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def configuracoes_validadas() -> AppSettings:
    """Carrega o config.json e valida contra o schema Pydantic."""
    config_path = RAIZ_PROJETO / "config.json"

    if not config_path.exists():
        raise FileNotFoundError(f"Arquivo config.json não encontrado em {config_path}")

    with config_path.open(encoding="utf-8") as f:
        dados = json.load(f)
    
    return AppSettings(**dados)

def configuracoes() -> dict[str, Any]:
    """Mantém compatibilidade com o código legado retornando um dict."""
    return configuracoes_validadas().model_dump()


def invalidar_cache() -> None:
    """Invalida o cache de configurações."""
    configuracoes_validadas.cache_clear()


# ---------------------------------------------------------------------------
# Resolução de caminhos
# ---------------------------------------------------------------------------

def resolver_path(path_relativo: str) -> str:
    """Resolve um caminho absoluto normalizado."""
    cfg = configuracoes_validadas()
    root_dir = cfg.paths.root_dir
    perfil_usuario = os.environ.get("USERPROFILE", os.path.expanduser("~"))

    return str(Path(perfil_usuario) / root_dir / path_relativo)


def resolver_path_relatorio(chave_fundo: str) -> str:
    """Resolve o caminho absoluto do arquivo de relatório gerencial."""
    cfg = configuracoes_validadas()
    if chave_fundo not in cfg.arquivo_gerencial:
        raise KeyError(f"Fundo '{chave_fundo}' não mapeado em 'arquivo_gerencial'")
    
    nome_arquivo = cfg.arquivo_gerencial[chave_fundo]
    diretorio_relatorio = cfg.paths.relatorio_diario
    return resolver_path(str(Path(diretorio_relatorio) / nome_arquivo))


def resolver_path_carteira(chave_fundo: str) -> str:
    """Resolve o caminho absoluto da carteira diária."""
    cfg = configuracoes_validadas()
    if chave_fundo not in cfg.carteiras:
        raise KeyError(f"Fundo '{chave_fundo}' não mapeado em 'carteiras'")
        
    path_relativo = cfg.carteiras[chave_fundo]
    return resolver_path(path_relativo)


def obter_contas_pagar_fundo(chave_fundo: str) -> list[str]:
    """Retorna a lista de palavras-chave de contas a pagar."""
    cfg = configuracoes_validadas()
    fundo_cfg = cfg.configuracoes_fundos.get(chave_fundo)
    return fundo_cfg.contas_pagar if fundo_cfg else []
