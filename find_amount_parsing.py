import os
import re

for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py') and not file.startswith('find_'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if 'float(' in content or 'int(' in content:
                    # Let's try to find potential missing `.replace(',', '.')`
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if 'float(' in line and 'message.text' in line:
                            if '.replace' not in line and '.replace' not in lines[i-1] if i > 0 else True:
                                print(f"POTENTIAL PARSING ISSUE: {path}:{i+1} : {line.strip()}")
