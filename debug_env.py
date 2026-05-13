from src.config.settings import configuracoes_validadas
import os

print(f"ROOT_DIR no env: {os.getenv('ROOT_DIR')}")
try:
    cfg = configuracoes_validadas()
    print(f"ROOT_DIR no Pydantic: {cfg.paths.root_dir}")
except Exception as e:
    print(f"ERRO: {e}")
