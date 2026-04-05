import os
import re

# BULBA missing config issue
path = "BULBA/BULBA/config.py"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "COMMISSION_PERCENT" not in content:
        content += "\nCOMMISSION_PERCENT = int(os.environ.get('COMMISSION_PERCENT', 30))\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

