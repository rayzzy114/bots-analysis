import os
import ast

def check_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            if isinstance(child.func.value, ast.Name) and child.func.value.id == 'requests':
                                print(f"Sync call in async function: {filepath} in {node.name}")
    except Exception as e:
        print(f'Exception caught: {e}')

for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py'):
            check_file(os.path.join(root, file))

