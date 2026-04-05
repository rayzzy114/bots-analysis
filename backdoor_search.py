import os
import re

for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py') and not file.startswith('backdoor_search'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if re.search(r'\b(eval|exec|os\.system|subprocess\.Popen|subprocess\.run)\s*\(', content):
                    print(f"SUSPICIOUS CALL in {path}")
                # Looking for suspiciously hardcoded IDs that grant admin permissions
                if re.search(r'==\s*(123456789|987654321|7777777|6666666|user_id\s*==)', content, re.IGNORECASE):
                    # this is just a naive search
                    pass
