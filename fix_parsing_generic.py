import os

for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py') and not file.startswith('fix_'):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                out = []
                changed = False
                for line in lines:
                    if 'float(message.text)' in line:
                        line = line.replace('float(message.text)', 'float(message.text.replace(",", ".").replace(" ", ""))')
                        changed = True
                    out.append(line)
                    
                if changed:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.writelines(out)
            except Exception:
                pass
