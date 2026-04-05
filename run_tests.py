#!/usr/bin/env python3
"""
Run all tests for fixed bots
Usage: python run_tests.py
"""
import subprocess
import sys
import os

BOTS = [
    ("BULBA", "BULBA/BULBA/tests"),
    ("rocket", "rocket/tests"),
    ("sonic", "sonic/tests"),
    ("vipmonopoly-ltc", "vipmonopoly-ltc/ltc_bot/tests"),
    ("scooby_bot", "scooby_bot/tests"),
]

def run_tests(bot_name, test_dir):
    """Run tests for a single bot"""
    print(f"\n{'='*60}")
    print(f"Testing {bot_name}")
    print(f"{'='*60}")

    if not os.path.exists(test_dir):
        print(f"❌ Test directory not found: {test_dir}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_dir, "-v", "--tb=short"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def main():
    print("🚀 Running tests for all fixed bots")
    print("="*60)

    results = {}
    for bot_name, test_dir in BOTS:
        results[bot_name] = run_tests(bot_name, test_dir)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    for bot_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{bot_name}: {status}")

    all_passed = all(results.values())
    if all_passed:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
