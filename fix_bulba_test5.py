import os
import re

path = "BULBA/BULBA/tests/test_rates.py"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    out = []
    for line in lines:
        if "assert 'LTC' in rates" in line:
            # fix indentation error again
            out.append(line.lstrip() + "\n")
        else:
            out.append(line)
            
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(out)

