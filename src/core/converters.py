"""
Funções puras de conversão e parsing de dados financeiros.

Este módulo é a **única fonte de verdade** para todas as transformações
de dados: conversão monetária, parsing de seções de planilha e
classificação de contas.

Design:
    - Todas as funções são puras (sem estado, sem efeitos colaterais).
    - Testáveis de forma isolada sem precisar de arquivos Excel reais.
    - Nenhuma dependência de outras partes do sistema — apenas pandas.

Compatibilidade futura com banco de dados:
    - Estas funções recebem e retornam DataFrames/scalars puros.
    - Quando migrar para DB, o código de ETL continuará usando estas
      funções; apenas a fonte dos dados (Excel → SQL) muda.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Conversão de valores monetários
# ---------------------------------------------------------------------------


def converter_moeda(valor: Any) -> float:
    """Converte representações monetárias variadas para float.

    Suporta os formatos mais comuns encontrados nas planilhas das
    administradoras:
        - Strings com ponto de milhar e vírgula decimal: "1.234,56" → 1234.56
        - Valores entre parênteses (negativo): "(500,00)" → -500.0
        - Float/int passados diretamente: 123.45 → 123.45
        - Valores nulos/vazios: None, "", NaN → 0.0

    Args:
        valor: Valor a converter. Pode ser str, float, int ou None.

    Returns:
        float: Valor numérico correspondente. Retorna 0.0 para entradas inválidas.

    Examples:
        >>> converter_moeda("1.234,56")
        1234.56
        >>> converter_moeda("(500,00)")
        -500.0
        >>> converter_moeda(None)
        0.0
        >>> converter_moeda(123.45)
        123.45
    """
    if pd.isna(valor) or str(valor).strip() == "":
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)

    try:
        texto = str(valor).strip()
        negativo = "(" in texto and ")" in texto
        # Remove tudo exceto dígitos, vírgula e hífen
        limpo = re.sub(r"[^\d,\-]", "", texto)
        if not limpo or limpo == ",":
            return 0.0
        numero = float(limpo.replace(",", "."))
        return -abs(numero) if negativo else numero
    except (ValueError, TypeError):
        return 0.0


def limpar_valor_monetario(valor: Any) -> float:
    """Normaliza valores com ponto de milhar e vírgula decimal.

    Variante simplificada de ``converter_moeda`` para strings no formato
    brasileiro ("1.234,56") sem suporte a parênteses ou negativos.

    Útil para pré-processar colunas de cotas onde os valores nunca são negativos.

    Args:
        valor: Valor a normalizar.

    Returns:
        float: Valor numérico. Retorna 0.0 para entradas inválidas.
    """
    if pd.isna(valor) or valor == "":
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    try:
        return float(str(valor).replace(".", "").replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Parsing de estrutura de planilhas
# ---------------------------------------------------------------------------


def resetar_cabecalho(df: pd.DataFrame) -> pd.DataFrame:
    """Promove a primeira linha do DataFrame como cabeçalho de colunas.

    Operação comum em planilhas onde a linha de cabeçalho não está
    na posição padrão — o Excel costuma ter dados de metadados nas
    primeiras linhas.

    Args:
        df: DataFrame cujos dados de cabeçalho estão na primeira linha.

    Returns:
        pd.DataFrame: DataFrame com colunas renomeadas e a linha
            do cabeçalho removida. Retorna DataFrame vazio se a
            entrada for inválida.
    """
    if df is None or df.empty or len(df) < 1:
        return pd.DataFrame()
    try:
        df = df.copy()
        df.columns = df.iloc[0]
        return df.iloc[1:].reset_index(drop=True)
    except Exception:
        return df


def encontrar_linha_categoria(
    df: pd.DataFrame,
    nome_categoria: str,
    coluna: str | None = None,
) -> int | None:
    """Localiza o índice da primeira linha onde *nome_categoria* é encontrado.

    Args:
        df: DataFrame a ser pesquisado.
        nome_categoria: Texto exato a localizar.
        coluna: Nome da coluna onde buscar. Se None, usa a primeira coluna.

    Returns:
        int | None: Índice da linha encontrada, ou None se não existir.

    Example:
        >>> linha = encontrar_linha_categoria(df, "VALORES A PAGAR", "Unnamed: 0")
    """
    serie = df[coluna] if coluna else df.iloc[:, 0]
    indices = df.index[serie == nome_categoria].tolist()
    return indices[0] if indices else None


def extrair_secao(
    df: pd.DataFrame,
    linha_inicio: int,
    linha_fim: int,
) -> pd.DataFrame:
    """Extrai uma seção do DataFrame entre dois índices.

    Remove linhas inteiramente nulas (comuns em layouts de planilhas
    com espaços decorativos) e promove a primeira linha como cabeçalho.

    Args:
        df: DataFrame completo da planilha.
        linha_inicio: Índice da primeira linha da seção (inclusive).
        linha_fim: Índice da última linha da seção (exclusive).

    Returns:
        pd.DataFrame: Subconjunto do DataFrame com cabeçalho normalizado.
            Retorna DataFrame vazio se o intervalo for inválido.
    """
    if linha_inicio >= linha_fim:
        return pd.DataFrame()

    secao = df.iloc[linha_inicio:linha_fim].reset_index(drop=True)
    secao = secao.dropna(how="all").reset_index(drop=True)
    return resetar_cabecalho(secao)


def detectar_coluna(df: pd.DataFrame, candidatos: list[str]) -> str | None:
    """Retorna o primeiro candidato encontrado como coluna do DataFrame.

    A busca é feita em duas passagens:
        1. Correspondência exata (respeita capitalização).
        2. Correspondência case-insensitive (cobre variações de acento).

    Args:
        df: DataFrame cujas colunas serão inspecionadas.
        candidatos: Lista de nomes candidatos em ordem de preferência.

    Returns:
        str | None: Nome real da coluna encontrada, ou None se nenhum candidato
            corresponder.

    Example:
        >>> col = detectar_coluna(df, ["Histórico", "Historico", "DESCRIÇÃO"])
    """
    colunas = list(df.columns)
    # Passagem 1: exata
    for candidato in candidatos:
        if candidato in colunas:
            return candidato
    # Passagem 2: case-insensitive
    colunas_lower = [str(c).lower() for c in colunas]
    for candidato in candidatos:
        try:
            idx = colunas_lower.index(candidato.lower())
            return colunas[idx]
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Classificação e agrupamento de contas
# ---------------------------------------------------------------------------


def classificar_contas(
    df: pd.DataFrame,
    coluna_descricao: str,
    coluna_valor: str,
    palavras_chave: list[str],
) -> pd.DataFrame:
    """Normaliza descrições e classifica contas em categorias padrão.

    Algoritmo:
        1. Converte ``coluna_valor`` para numérico.
        2. Para cada ``palavra_chave``, substitui as descrições correspondentes
           pelo próprio termo capitalizado (ex: "gestão" → "Gestão").
        3. Descrições não substituídas são classificadas como
           "Contas a receber" (valor > 0) ou "Contas a pagar" (valor ≤ 0).
        4. Agrupa pelo nome final e soma os valores.

    Args:
        df: DataFrame com as contas brutas.
        coluna_descricao: Nome da coluna que contém as descrições/históricos.
        coluna_valor: Nome da coluna com os valores financeiros.
        palavras_chave: Lista de termos para identificação das categorias
            conhecidas (ex: ["gestão", "anbima", "custódia"]).

    Returns:
        pd.DataFrame: DataFrame agrupado e ordenado por valor crescente,
            com colunas ``coluna_descricao`` e ``coluna_valor``.

    Example:
        >>> resultado = classificar_contas(
        ...     df_contas, "Histórico", "Valor Total",
        ...     ["gestão", "anbima", "auditoria"]
        ... )
    """
    df = df.copy()
    df[coluna_valor] = pd.to_numeric(df[coluna_valor], errors="coerce").fillna(0.0)

    descricoes = df[coluna_descricao].astype(str).str.lower()
    chaves_lower = [p.lower() for p in palavras_chave]

    # Substitui cada correspondência pelo termo capitalizado
    for chave in chaves_lower:
        mascara = descricoes.str.contains(chave, na=False)
        df.loc[mascara, coluna_descricao] = chave.capitalize()

    # Classifica o restante como pagar/receber
    nao_substituido = ~df[coluna_descricao].str.lower().isin(chaves_lower)
    df.loc[nao_substituido, coluna_descricao] = df.loc[
        nao_substituido, coluna_valor
    ].apply(lambda v: "Contas a receber" if v > 0 else "Contas a pagar")

    return (
        df.groupby(coluna_descricao, as_index=False)[coluna_valor]
        .sum()
        .sort_values(coluna_valor)
        .reset_index(drop=True)
    )


def buscar_valor_em_dataframe(
    df: pd.DataFrame,
    categoria: str,
    coluna_descricao: str,
    coluna_valor: str | int,
    busca_parcial: bool = False,
) -> float:
    """Recupera um valor escalar do DataFrame pelo identificador da linha.

    Args:
        df: DataFrame onde realizar a busca.
        categoria: Texto identificador da linha desejada.
        coluna_descricao: Nome da coluna de identificação.
        coluna_valor: Nome ou índice inteiro da coluna de valor.
        busca_parcial: Se True, usa ``str.contains`` em vez de igualdade exata.

    Returns:
        float: Valor encontrado. Retorna 0.0 se não encontrado ou em erro.

    Example:
        >>> valor = buscar_valor_em_dataframe(
        ...     df_contas, "Gestão", "Histórico", "Valor Total"
        ... )
    """
    try:
        if busca_parcial:
            filtro = df[coluna_descricao].str.contains(categoria, case=False, na=False)
        else:
            filtro = df[coluna_descricao] == categoria

        if isinstance(coluna_valor, int):
            resultado = df.loc[filtro].values
            return float(resultado[0, coluna_valor]) if len(resultado) > 0 else 0.0

        resultado = df.loc[filtro, coluna_valor]
        return float(resultado.iloc[0]) if not resultado.empty else 0.0
    except Exception:
        return 0.0


def encontrar_linhas_marcadores(
    df: pd.DataFrame,
    marcadores: dict[str, list[str]],
    coluna: str,
) -> dict[str, str]:
    """Localiza marcadores de seção em uma coluna do DataFrame.

    Testa cada lista de variantes do marcador (exata → case-insensitive parcial)
    e retorna o primeiro texto real encontrado para cada chave.

    Args:
        df: DataFrame da planilha.
        marcadores: Dicionário ``{chave: [variante1, variante2, ...]}``.
        coluna: Nome da coluna onde buscar os marcadores.

    Returns:
        dict[str, str]: Mapeamento ``{chave: texto_real_encontrado}``.
            Chaves cujos marcadores não foram encontrados são omitidas.

    Example:
        >>> MARCADORES = {
        ...     "contas_pagar": ["Valores a Pagar", "VALORES A LIQUIDAR"],
        ...     "resumo": ["RESUMO DA CARTEIRA", "Resumo Carteira"],
        ... }
        >>> encontrados = encontrar_linhas_marcadores(df, MARCADORES, "Carteira")
    """
    valores_coluna = df[coluna].dropna().astype(str).str.strip().tolist()
    encontrados: dict[str, str] = {}

    for chave, variantes in marcadores.items():
        # Passagem 1: exata
        for variante in variantes:
            if variante in valores_coluna:
                encontrados[chave] = variante
                break
        else:
            # Passagem 2: case-insensitive parcial
            for variante in variantes:
                correspondencias = [v for v in valores_coluna if variante.lower() in v.lower()]
                if correspondencias:
                    encontrados[chave] = correspondencias[0]
                    break

    return encontrados
