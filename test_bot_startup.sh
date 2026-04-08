#!/bin/bash
# Bot startup test - runs each bot for 5 seconds with test token
# Token passed via environment variable TEST_BOT_TOKEN

TOTAL=0
PASS=0
FAIL=0
SKIP=0

echo "========================================"
echo " BOT STARTUP TEST SUITE"
echo " Token: ${TEST_BOT_TOKEN:0:20}..."
echo " Timeout: 5s per bot"
echo "========================================"
echo ""

run_bot() {
    local dir="$1"
    local entry="$2"
    local label="$3"
    TOTAL=$((TOTAL + 1))

    echo -n "[$TOTAL] $label ... "

    # Run bot for 5 seconds
    local output
    local exitcode
    output=$(cd "$dir" && timeout 5 uv run python "$entry" 2>&1) || exitcode=$?

    # Check for errors
    if [[ $exitcode -eq 124 ]]; then
        # Timeout (expected - bot runs forever)
        # Check if there were any errors before timeout
        local errors
        errors=$(echo "$output" | grep -iE "error|exception|traceback|crash|failed" || true)
        if [[ -n "$errors" ]]; then
            echo "❌ ERRORS FOUND"
            echo "    $errors"
            FAIL=$((FAIL + 1))
        else
            echo "✅ OK"
            PASS=$((PASS + 1))
        fi
    elif [[ $exitcode -eq 0 ]]; then
        # Bot exited normally (might be expected for some bots)
        echo "✅ OK (clean exit)"
        PASS=$((PASS + 1))
    else
        # Non-zero exit = crash
        echo "❌ CRASHED (exit $exitcode)"
        local errors
        errors=$(echo "$output" | tail -20)
        echo "    $errors"
        FAIL=$((FAIL + 1))
    fi
}

# Skip files (duplicates, backups, non-entry-points)
skip_files="
infinity_clone_bot_backup/main.py
lucky_original_production/main.py
lucky_original_production/web/main.py
sprut/sprut/bot.py
vip monopoly - all crypto/monopoly_old/main.py
"

is_skipped() {
    local path="$1"
    for sf in $skip_files; do
        if [[ "$path" == *"$sf"* ]]; then
            return 0
        fi
    done
    return 1
}

# Run all bots
run_bot "." "60sec/bot.py" "60sec"
run_bot "." "BITMAFIA/bitmafia_clone/main.py" "BITMAFIA"
run_bot "." "BITMAGNIT/main.py" "BITMAGNIT"
run_bot "." "BULBA/BULBA/bot.py" "BULBA"
run_bot "." "MIXMAFIA/mixmafia_clone/main.py" "MIXMAFIA"
run_bot "." "VortexExchange/main.py" "VortexExchange"
run_bot "." "banana/banana/main.py" "banana"
run_bot "." "bitbot/main.py" "bitbot"
run_bot "." "btc_monopoly_bot/main.py" "btc_monopoly_bot"
run_bot "." "donald/bot.py" "donald"
run_bot "." "duck/duck/main.py" "duck"
run_bot "." "ex24pro_clone/ex24_final/bot.py" "ex24pro"
run_bot "." "expresschanger/10/bot.py" "expresschanger"
run_bot "." "hassle01/hassle/main.py" "hassle01"
run_bot "." "hottabych/hottabych/main.py" "hottabych"
run_bot "." "infinity_clone_bot/main.py" "infinity_clone_bot"
run_bot "." "laitbit/main.py" "laitbit"
run_bot "." "ltc_bot/main.py" "ltc_bot (vipmonopoly-ltc)"
run_bot "." "lucky_original_production/bot/main.py" "lucky_original_production"
run_bot "." "mario/main.py" "mario"
run_bot "." "mask/main.py" "mask"
run_bot "." "menyala_bot/main.py" "menyala_bot"
run_bot "." "mm5btc_bot/main.py" "mm5btc_bot"
run_bot "." "rapid/main.py" "rapid"
run_bot "." "rocket/main.py" "rocket"
run_bot "." "scooby/scooby/main.py" "scooby"
run_bot "." "scooby_bot/scooby/main.py" "scooby_bot"
run_bot "." "shaxta/main.py" "shaxta"
run_bot "." "sonic/main.py" "sonic"
run_bot "." "sprut/bot.py" "sprut"
run_bot "." "vipmonopoly-btc/monopoly/main.py" "vipmonopoly-btc"
run_bot "." "vipmonopoly-ltc/ltc_bot/main.py" "vipmonopoly-ltc"
run_bot "." "vipmonopoly-xmr/xmr_bor/main.py" "vipmonopoly-xmr"

echo ""
echo "========================================"
echo " RESULTS: $PASS passed, $FAIL failed, $TOTAL total"
echo "========================================"

exit $FAIL
