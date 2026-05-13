import os 
import json
import pandas as pd
from Carteira import * 
from funcoes_uteis import *

from src.config.settings import configuracoes, resolver_path

# --- Configuração e Helpers ---

CONFIG = configuracoes()

def obter_path_absoluto(path_relativo):
    """Resolve caminhos usando o novo sistema de settings."""
    return resolver_path(path_relativo)

def limpar_valor(valor):
    """Padroniza a limpeza de valores monetários."""
    if pd.isna(valor) or valor == "":
        return 0.0
    if isinstance(valor, str):
        try:
            # Remove pontos de milhar e troca vírgula por ponto
            return float(valor.replace(".", "").replace(",", "."))
        except ValueError:
            return 0.0
    return float(valor)

def obter_valor_ordem(df, ordem, coluna):
    """Busca um valor com base na coluna 'Ordem'. Retorna 0.0 se não encontrar."""
    if 'Ordem' not in df.columns:
        return 0.0
    try:
        ordem_str = str(ordem)
        mascara = df['Ordem'].astype(str).str.replace(r'\.0$', '', regex=True) == ordem_str
        resultado = df.loc[mascara, coluna].values
        return float(resultado[0]) if len(resultado) > 0 else 0.0
    except (KeyError, IndexError, ValueError):
        return 0.0

# --- Fim dos Helpers ---
# Nota: Funções legadas de gerar_carteira_* foram removidas e migradas para o src.registry.
