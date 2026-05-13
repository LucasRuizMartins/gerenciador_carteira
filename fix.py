import os

def fix_future(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    future_idx = -1
    for i, line in enumerate(lines):
        if line.startswith('from __future__'):
            future_idx = i
            break
            
    if future_idx > 0:
        # Check if there are imports before it
        for i in range(future_idx):
            if lines[i].startswith('import ') or lines[i].startswith('from '):
                # Move future to the top of imports
                future_line = lines.pop(future_idx)
                lines.insert(i, future_line)
                break
                
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

files = ['Carteira.py', 'src/services/excel_writer.py', 'src/registry.py']
for f in files:
    fix_future(f)
print("fixed")
