import os

path = "BULBA/BULBA/tests/test_rates.py"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    out = []
    for line in lines:
        if line.strip() == "pass":
            out.append("        pass\n")
        else:
            out.append(line)
            
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(out)

