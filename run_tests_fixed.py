import sys
import os

# Create missing dot env
with open('.env', 'w') as f:
    f.write('BOT_TOKEN="dummy:token"\n')

os.system("export PYTHONPATH=scooby_bot/scooby/src:rocket:BULBA:scooby_bot:$PYTHONPATH && python3 run_tests.py")
