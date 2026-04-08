import subprocess
import os
import sys

# Add the current directory to sys.path so bots can import 'app' or 'core'
sys.path.append(os.getcwd())

bot_dirs = [d for d in os.listdir('.') if os.path.isdir(d) and not d.startswith('.') and d not in ['shared_lib', 'tmp']]

print(f"Starting corrected test suite for {len(bot_dirs)} bots...\n")

results = {}

for bot in bot_dirs:
    test_path = os.path.join(bot, 'tests')
    if os.path.exists(test_path):
        print(f"Testing {bot}...")
        
        # Set PYTHONPATH to include the current bot's directory
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.abspath(bot) + ":" + os.getcwd()
        
        # Use simple python discovery
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", test_path], 
            capture_output=True, text=True, env=env
        )
        
        if result.returncode == 0:
            results[bot] = "PASSED"
            print(f"  Result: PASSED")
        else:
            results[bot] = "FAILED"
            print(f"  Result: FAILED")
            # Only print the first few lines of errors to keep output clean
            print("\n".join(result.stderr.splitlines()[-5:]))
    else:
        results[bot] = "SKIPPED (No tests)"

print("\n--- Final Summary ---")
for bot, status in sorted(results.items()):
    print(f"{bot}: {status}")
