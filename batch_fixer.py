import os
import re

def fix_bot(bot_path):
    # Fix SettingsManager (regex issue)
    for root, dirs, files in os.walk(bot_path):
        if 'storage.py' in files:
            file_path = os.path.join(root, 'storage.py')
            with open(file_path, 'r') as f:
                content = f.read()
            if 'class SettingsStore' in content and 'process_text' in content and 're.sub' not in content:
                print(f"  Fixing process_text in {file_path}")
                new_content = re.sub(
                    r'(def process_text.*?return.*?)(text\.format\(.*?data\))',
                    r'\1 re.sub(r"{(\\w+)}", lambda m: self.data["links"].get(m.group(1), "Администратор"), text)',
                    content, flags=re.DOTALL
                )
                with open(file_path, 'w') as f:
                    f.write(new_content)

BOTS = [
    '60sec', 'BITMAFIA', 'BITMAGNIT', 'BULBA', 'MIXMAFIA', 'REDBULL', 'VortexExchange',
    'banana', 'bitbot', 'btc_monopoly_bot', 'donald', 'duck', 'ex24pro_clone',
    'expresschanger', 'hassle01', 'hottabych', 'infinity_clone_bot',
    'infinity_clone_bot_backup', 'laitbit', 'ltc_bot', 'lucky_original_production',
    'mario', 'mask', 'menyala_bot', 'mixer-money-site', 'mm5btc_bot', 'rapid',
    'rocket', 'scooby', 'scooby_bot', 'shaxta', 'sonic', 'sprut',
    'vip monopoly - all crypto', 'vipmonopoly-btc', 'vipmonopoly-ltc',
    'vipmonopoly-xmr', 'yaga'
]

for bot in BOTS:
    bot_path = os.path.join('/home/roxy/projects/bots', bot)
    if os.path.exists(bot_path):
        fix_bot(bot_path)
