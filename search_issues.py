import asyncio
import os
import re

def search():
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            # Hidden backdoors
                            if re.search(r'eval\(|exec\(|os\.system|subprocess\.', line):
                                print(f"SUSPICIOUS: {filepath}:{i+1}: {line.strip()}")
                            # Incorrect API handling (e.g. not checking response status)
                            if 'requests.get' in line or 'requests.post' in line:
                                print(f"API: {filepath}:{i+1}: {line.strip()}")
                            if 'aiohttp.ClientSession' in line:
                                print(f"AIOHTTP: {filepath}:{i+1}: {line.strip()}")
                            # Silent failures
                            if line.strip() == 'except:' or line.strip() == 'except Exception:':
                                if i + 1 < len(lines) and 'pass' in lines[i+1]:
                                    print(f"SILENT_EXCEPT: {filepath}:{i+1}: {line.strip()}")
                                    print(f"               {lines[i+1].strip()}")
                            # Async issues (e.g., blocking call in async)
                            if 'requests.get' in line and 'async def' in content:
                                # Just a guess
                                pass
                except Exception as e:
                    print(f'Exception caught: {e}')

search()
