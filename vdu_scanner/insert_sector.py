import os
import glob

def insert_sector(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified = False
    
    if '"Symbol": r[\'symbol\'],' in content:
        if 'get_stock_sector' not in content:
            content = 'from data_fetcher import get_stock_sector\n' + content
        content = content.replace('"Symbol": r[\'symbol\'],', '"Symbol": r[\'symbol\'],\n                "Sector": get_stock_sector(r[\'symbol\']),')
        modified = True
        
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")

for f in glob.glob('*.py') + glob.glob('tabs/*.py'):
    insert_sector(f)
    
print("Done")
