import os
import glob

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    content = content.replace('"Company Name": r[\'company_name\'],\n', '')
    content = content.replace('"Company Name": lambda x: (x.get(\'company_name\') or get_company_name(x.get(\'symbol\', \'\')) or "").upper(),\n', '')
    
    # In app.py render_unified_strategy_table:
    # 1. remove company_name cell
    content = content.replace('cells.append(f\'<td style="padding: 10px 12px; color: #94a3b8; font-size: 0.82rem;">{r.get("company_name") or get_company_name(r["symbol"])}</td>\')\n', '')
    
    # 2. headers replacement
    content = content.replace('headers = ["Watchlist", "Symbol", "Sector", "CMP"]', 'headers = ["Watchlist", "Symbol", "Sector", "CMP"]')
    
    # 3. column configs replacement in data_editor
    content = content.replace('"company_name": st.column_config.TextColumn("Company Name", disabled=True),\n', '')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for f in glob.glob('*.py') + glob.glob('tabs/*.py'):
    process_file(f)
    
print("Done")
