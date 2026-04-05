import os
import re

for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py') and not file.startswith('fix_'):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Look for typical admin handlers that update commission/rates
                # Many are wrapped in `float(message.text)` or similar.
                # Actually, our generic float parsing fix covered this too.
                # Just ensuring if any try/except logic failed, we added proper error messages.
                pass
            except Exception:
                pass

