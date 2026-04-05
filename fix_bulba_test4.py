import os
import re

path = "BULBA/BULBA/tests/test_rates.py"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    out = []
    for line in lines:
        if "assert inspect.iscoroutinefunction" in line:
            # fix indentation error
            out.append(line.lstrip() + "\n")
        else:
            out.append(line)
            
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(out)

