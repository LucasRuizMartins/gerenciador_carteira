import os
import re

def process_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    has_import = any('get_logger' in line for line in lines)
    if not has_import:
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                lines.insert(i, 'from src.core.logger import get_logger\nlogger = get_logger(__name__)\n')
                break
                
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if 'print(' in line and not line.strip().startswith('#'):
            # simple single line prints
            if 'Erro' in line or 'ERRO' in line:
                line = line.replace('print(', 'logger.error(')
            elif 'Aviso' in line or 'AVISO' in line:
                line = line.replace('print(', 'logger.warning(')
            elif 'Falha' in line:
                line = line.replace('print(', 'logger.error(')
            else:
                line = line.replace('print(', 'logger.info(')
        new_lines.append(line)
        i += 1
        
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

files = ['Carteira.py', 'funcoes_uteis.py', 'src/services/excel_writer.py', 'src/registry.py', 'executar_carteira.py']
for f in files:
    process_file(f)
print("done")
