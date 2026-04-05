import os
import ast

def check_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'sqlite3' in content and 'async def' in content:
                print(f"File with sqlite3 and async def: {filepath}")
    except Exception as e:
        print(f'Exception caught: {e}')

for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py'):
            check_file(os.path.join(root, file))

