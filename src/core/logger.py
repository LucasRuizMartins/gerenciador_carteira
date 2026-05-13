import logging
import os
from datetime import datetime
from src.config.settings import configuracoes

# Variável global para garantir que os handlers sejam adicionados apenas uma vez
_LOGGER_CONFIGURADO = False

def get_logger(name: str) -> logging.Logger:
    """Configura e retorna um logger padronizado para o sistema.
    
    Grava logs tanto no console (stdout) quanto em arquivo dentro 
    da pasta configurada em config.json ou em 'logs/'.
    
    Args:
        name: Nome do módulo que está chamando o logger (usualmente __name__)
        
    Returns:
        logging.Logger: Instância configurada do logger.
    """
    global _LOGGER_CONFIGURADO
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Se já foi configurado (por exemplo, na inicialização principal), 
    # apenas retorna a instância para não duplicar handlers
    if _LOGGER_CONFIGURADO or logger.hasHandlers():
        return logger
        
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler de Console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler de Arquivo
    try:
        cfg = configuracoes()
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_dir = os.path.join(base_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        data_atual = datetime.now().strftime('%Y%m%d')
        file_handler = logging.FileHandler(
            os.path.join(log_dir, f'carteira_{data_atual}.log'), 
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # Se falhar ao criar o arquivo, usa apenas console
        logger.warning(f"Não foi possível configurar arquivo de log: {e}")
        
    _LOGGER_CONFIGURADO = True
    return logger
