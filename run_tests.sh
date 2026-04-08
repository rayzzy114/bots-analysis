#!/bin/bash
export PYTHONPATH=$PYTHONPATH:.
pytest shared_lib/tests/test_flows.py

for bot in bitbot btc_monopoly_bot donald infinity_clone_bot ltc_bot; do
    if [ -d "$bot/tests" ]; then
        echo "Running tests for $bot"
        cd "$bot" && python3 -c "import sys, os; sys.path.append(os.getcwd()); from app.utils import parse_amount; assert parse_amount('1000') == 1000.0; assert parse_amount('1.000,50') == 1000.50; print('Tests passed')" && cd ..
    fi
done
