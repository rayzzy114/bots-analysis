import os
import re

files_to_fix = [
    './hassle01/hassle/main.py',
    './REDBULL/red/red bull/redbull exchange/main.py',
    './banana/banana/main.py',
    './duck/duck/main.py',
    './hottabych/hottabych/main.py',
    './hottabych/hottabych/hot.py',
    './sprut/bot.py',
    './sprut/sprut/bot.py'
]

def fix_file(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Replace "sqlite3.connect(X)" with "sqlite3.connect(X, check_same_thread=False, isolation_level=None)"
    # We will do a generic regex replace for standard connections.
    
    # regex match for sqlite3.connect('something') or sqlite3.connect(VARIABLE)
    # Be careful not to replace already fixed ones
    
    if 'check_same_thread=False' not in content:
        content = re.sub(r'sqlite3\.connect\((.*?)\)', r'sqlite3.connect(\1, check_same_thread=False, isolation_level=None)', content)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
for f in files_to_fix:
    fix_file(f)
