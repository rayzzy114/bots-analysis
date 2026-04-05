import os
import re

for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    # check if a hardcoded ID is used to bypass checks
                    if re.search(r'message\.from_user\.id\s*==\s*\d+', line):
                        print(f"HARDCODED ID in {path}:{i+1} : {line.strip()}")
                    if 'is_admin' in line.lower() and '==' in line and any(c.isdigit() for c in line):
                        print(f"POTENTIAL ADMIN BACKDOOR in {path}:{i+1} : {line.strip()}")

