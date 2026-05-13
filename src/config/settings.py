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


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_CONFIG_FILENAME = "config.json"


# ---------------------------------------------------------------------------
# Carregamento e cache
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def configuracoes() -> dict[str, Any]:
    """Carrega e cacheia o arquivo config.json.

    O cache garante que o arquivo é lido apenas uma vez por execução,
    mesmo que a função seja chamada múltiplas vezes.

    Returns:
        dict: Dicionário completo com todas as configurações do sistema.

    Raises:
        FileNotFoundError: Se config.json não for encontrado.
        json.JSONDecodeError: Se o arquivo estiver malformado.
    """
    # Resolve sempre relativo à raiz do projeto (dois níveis acima de src/config/)
    raiz_projeto = Path(__file__).resolve().parent.parent.parent
    config_path = raiz_projeto / _CONFIG_FILENAME

    if not config_path.exists():
        raise FileNotFoundError(
            f"Arquivo de configuração não encontrado: {config_path}\n"
            "Certifique-se de que config.json está na raiz do projeto."
        )

    with config_path.open(encoding="utf-8") as f:
        return json.load(f)


def invalidar_cache() -> None:
    """Invalida o cache de configurações.

    Útil em testes unitários que precisam trocar a configuração
    entre casos de teste.
    """
    configuracoes.cache_clear()


# ---------------------------------------------------------------------------
# Resolução de caminhos
# ---------------------------------------------------------------------------


def resolver_path(path_relativo: str) -> str:
    """Resolve um caminho relativo ao diretório raiz do usuário.

    Combina USERPROFILE (Windows) com o root_dir definido em config.json
    e o path_relativo fornecido.

    Args:
        path_relativo: Caminho relativo à raiz dos documentos Carmel Capital
            (ex: "01 - OPERACIONAL/CONTROLADORIA/...").

    Returns:
        str: Caminho absoluto normalizado para o sistema operacional atual.

    Example:
        >>> path = resolver_path(configuracoes()["carteiras"]["FIDARA"])
        >>> # C:\\Users\\Nowtek\\Carmel Capital\\...\\FIDARA.xlsb
    """
    cfg = configuracoes()
    root_dir: str = cfg["paths"]["root_dir"]
    perfil_usuario = os.environ.get("USERPROFILE", os.path.expanduser("~"))

    # Usa pathlib para normalizar separadores independente do SO
    return str(Path(perfil_usuario) / root_dir / path_relativo)


def resolver_path_relatorio(chave_fundo: str) -> str:
    """Resolve o caminho absoluto do arquivo de relatório gerencial de um fundo.

    Args:
        chave_fundo: Chave do fundo em config.json['arquivo_gerencial']
            (ex: "FIDARA", "CDC").

    Returns:
        str: Caminho absoluto do arquivo .xlsb do relatório gerencial.

    Raises:
        KeyError: Se a chave_fundo não existir em config.json['arquivo_gerencial'].
    """
    cfg = configuracoes()
    nome_arquivo: str = cfg["arquivo_gerencial"][chave_fundo]
    diretorio_relatorio: str = cfg["paths"]["relatorio_diario"]
    return resolver_path(str(Path(diretorio_relatorio) / nome_arquivo))


def resolver_path_carteira(chave_fundo: str) -> str:
    """Resolve o caminho absoluto da carteira diária de um fundo.

    Args:
        chave_fundo: Chave do fundo em config.json['carteiras']
            (ex: "FIDARA", "CDC").

    Returns:
        str: Caminho absoluto do arquivo Excel da carteira diária.

    Raises:
        KeyError: Se a chave_fundo não existir em config.json['carteiras'].
    """
    cfg = configuracoes()
    path_relativo: str = cfg["carteiras"][chave_fundo]
    return resolver_path(path_relativo)


def obter_contas_pagar_fundo(chave_fundo: str) -> list[str]:
    """Retorna a lista de palavras-chave de contas a pagar de um fundo.

    Args:
        chave_fundo: Chave do fundo em config.json['configuracoes_fundos'].

    Returns:
        list[str]: Lista de categorias de contas a pagar.
            Retorna lista vazia se o fundo não tiver configuração.
    """
    cfg = configuracoes()
    fundo_cfg = cfg.get("configuracoes_fundos", {}).get(chave_fundo, {})
    return fundo_cfg.get("contas_pagar", [])
