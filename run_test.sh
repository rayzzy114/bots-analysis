#!/bin/bash
export BOT_TOKEN="8642974980:AAGWBBZDtYPLgUMutWaJA4l1JI1l1YNHJmY"
export ADMIN_IDS="12345"
export PYTHONUNBUFFERED=1

# Create .env for bots that read from it
export_env() {
    local dir="$1"
    if [[ -f "$dir/.env" ]]; then
        # Add our test vars to .env
        if ! grep -q "^BOT_TOKEN=" "$dir/.env"; then
            echo "BOT_TOKEN=$BOT_TOKEN" >> "$dir/.env"
        fi
        if ! grep -q "^ADMIN_IDS=" "$dir/.env"; then
            echo "ADMIN_IDS=$ADMIN_IDS" >> "$dir/.env"
        fi
    fi
}

TOTAL=0
PASS=0
FAIL=0

echo "============================================"
echo " BOT STARTUP TEST (5s each)"
echo " Token: ${BOT_TOKEN:0:20}..."
echo "============================================"
echo ""

test_bot() {
    local dir="$1"
    local entry="$2"
    local label="$3"
    TOTAL=$((TOTAL + 1))

    # Add env to .env if exists
    export_env "$dir"

    echo -n "[$TOTAL] $label ... "

    # Export BOT_TOKEN for this bot's dir
    local output
    local exitcode=0

    cd "$dir" 2>/dev/null || { echo "❌ DIR MISSING"; FAIL=$((FAIL+1)); cd /home/roxy/projects/bots; return; }

    output=$(timeout 5 python3 "$entry" 2>&1) || exitcode=$?

    cd /home/roxy/projects/bots

    if [[ $exitcode -eq 124 ]]; then
        # Timeout = bot is running (expected)
        local errors
        errors=$(echo "$output" | grep -iE "error:|exception|traceback|crash" | head -3 || true)
        if [[ -n "$errors" ]]; then
            echo "❌ ERRORS"
            echo "$errors" | sed 's/^/    /'
            FAIL=$((FAIL + 1))
        else
            echo "✅ OK"
            PASS=$((PASS + 1))
        fi
    elif [[ $exitcode -eq 0 ]]; then
        echo "✅ OK (clean exit)"
        PASS=$((PASS + 1))
    else
        echo "❌ EXIT $exitcode"
        echo "$output" | tail -10 | sed 's/^/    /'
        FAIL=$((FAIL + 1))
    fi
}

test_bot "." "60sec/bot.py" "60sec"
test_bot "." "BITMAFIA/bitmafia_clone/main.py" "BITMAFIA"
test_bot "." "BITMAGNIT/main.py" "BITMAGNIT"
test_bot "." "BULBA/BULBA/bot.py" "BULBA"
test_bot "." "MIXMAFIA/mixmafia_clone/main.py" "MIXMAFIA"
test_bot "." "VortexExchange/main.py" "VortexExchange"
test_bot "." "banana/banana/main.py" "banana"
test_bot "." "bitbot/main.py" "bitbot"
test_bot "." "btc_monopoly_bot/main.py" "btc_monopoly_bot"
test_bot "." "donald/bot.py" "donald"
test_bot "." "duck/duck/main.py" "duck"
test_bot "." "ex24pro_clone/ex24_final/bot.py" "ex24pro"
test_bot "." "expresschanger/10/bot.py" "expresschanger"
test_bot "." "hassle01/hassle/main.py" "hassle01"
test_bot "." "hottabych/hottabych/main.py" "hottabych"
test_bot "." "infinity_clone_bot/main.py" "infinity_clone_bot"
test_bot "." "laitbit/main.py" "laitbit"
test_bot "." "ltc_bot/main.py" "ltc_bot"
test_bot "." "lucky_original_production/bot/main.py" "lucky_original"
test_bot "." "mario/main.py" "mario"
test_bot "." "mask/main.py" "mask"
test_bot "." "menyala_bot/main.py" "menyala_bot"
test_bot "." "mm5btc_bot/main.py" "mm5btc_bot"
test_bot "." "rapid/main.py" "rapid"
test_bot "." "rocket/main.py" "rocket"
test_bot "." "scooby/scooby/main.py" "scooby"
test_bot "." "scooby_bot/scooby/main.py" "scooby_bot"
test_bot "." "shaxta/main.py" "shaxta"
test_bot "." "sonic/main.py" "sonic"
test_bot "." "sprut/bot.py" "sprut"
test_bot "." "vipmonopoly-btc/monopoly/main.py" "vipmonopoly-btc"
test_bot "." "vipmonopoly-ltc/ltc_bot/main.py" "vipmonopoly-ltc"
test_bot "." "vipmonopoly-xmr/xmr_bor/main.py" "vipmonopoly-xmr"

echo ""
echo "============================================"
echo " RESULTS: $PASS passed, $FAIL failed / $TOTAL total"
echo "============================================"
