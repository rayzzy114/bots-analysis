import os

files_to_check = [
    './sonic/main.py',
    './REDBULL/red/red bull/redbull exchange/main.py',
    './hassle01/hassle/main.py',
    './duck/duck/main.py',
    './banana/banana/main.py',
    './sprut/bot.py',
    './sprut/sprut/bot.py',
    './hottabych/hottabych/main.py',
    './hottabych/hottabych/hot.py',
    './btc_monopoly_bot/handlers/buy.py',
    './ltc_bot/handlers/buy.py',
    './shaxta/handlers/buy.py'
]

def check_file(filepath):
    if not os.path.exists(filepath):
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    out = []
    changed = False
    for i, line in enumerate(lines):
        # We look for naive float(message.text) and replace it with safe parser.
        # But wait, it's safer to just replace message.text in the float() call.
        if 'float(message.text)' in line:
            line = line.replace('float(message.text)', 'float(message.text.replace(",", ".").replace(" ", ""))')
            changed = True
        elif 'float(message.text.strip())' in line:
            line = line.replace('float(message.text.strip())', 'float(message.text.replace(",", ".").replace(" ", "").strip())')
            changed = True
            
        out.append(line)
        
    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(out)

for f in files_to_check:
    check_file(f)

