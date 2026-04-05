#!/bin/bash
# Run all bot tests
# Usage: ./run_tests.sh

set -e

BOTS_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo "Running tests for all fixed bots"
echo "========================================"

run_test() {
    local name=$1
    local dir=$2
    echo ""
    echo "Testing: $name"
    echo "----------------------------------------"
    cd "$BOTS_DIR/$dir"
    python3 -m pytest tests/ -v --tb=short -p no:anchorpy 2>/dev/null || \
    echo "No tests or tests failed"
}

run_test "rocket" "rocket"
run_test "sonic" "sonic"
run_test "vipmonopoly-ltc" "vipmonopoly-ltc/ltc_bot"

echo ""
echo "========================================"
echo "To run tests manually:"
echo "  cd <bot_dir> && python3 -m pytest tests/ -v"
echo "========================================"
