import os

def fix_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        changed = False
        for i in range(len(lines)):
            line = lines[i]
            if line.strip() in ['except:', 'except Exception:', 'except Exception as e:']:
                if i + 1 < len(lines) and 'pass' in lines[i+1]:
                    # Replace pass with logging
                    indent = lines[i+1][:len(lines[i+1]) - len(lines[i+1].lstrip())]
                    if 'as e:' in line:
                        lines[i+1] = f"{indent}print(f'Exception caught: {{e}}')\n"
                    else:
                        lines[i] = line.replace('except:', 'except Exception as e:').replace('except Exception:', 'except Exception as e:')
                        lines[i+1] = f"{indent}print(f'Exception caught: {{e}}')\n"
                    changed = True
                    
        if changed:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(lines)
    except Exception as e:
        print(f'Exception caught: {e}')

for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))

