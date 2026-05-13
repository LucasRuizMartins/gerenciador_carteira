import os 
import json
import pandas as pd
from Carteira import * 
from funcoes_uteis import *

# --- Configuração e Helpers ---

def carregar_config():
    base_path = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_path, 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

CONFIG = carregar_config()

def obter_path_absoluto(path_relativo):
    """Resolve caminhos relativos ao root_dir do config.json de forma dinâmica pelo usuário."""
    root = CONFIG['paths']['root_dir']
    user_profile = os.environ.get('USERPROFILE', os.path.expanduser('~'))
    return os.path.join(user_profile, root, path_relativo).replace('/', '\\')

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
