import os
import subprocess
import sys
from watchfiles import watch

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def run_bot():
    print(f"[*] Starting Bot from {BASE_DIR}...")
    # Используем sys.executable, чтобы запуститься тем же интерпретатором (venv)
    return subprocess.Popen([sys.executable, "-m", "bot.main"], cwd=BASE_DIR)


if __name__ == "__main__":

    process = run_bot()



    for changes in watch("bot", "core"):

        print(f"Detected changes in: {changes}")

        process.terminate()

        process.wait()

        process = run_bot()

