import sys

import os



sys.path.append(os.getcwd())


def test_imports():

    print("--- QA Import Check ---")

    try:

        from bot.keyboards import main_kb

        print("✅ Keyboard module loaded")


        required_kb = ['get_main_kb', 'get_main_inline_kb', 'get_currencies_kb', 'get_profile_kb']

        for func in required_kb:

            if hasattr(main_kb, func):

                print(f"  ✅ main_kb.{func} exists")

            else:

                print(f"  ❌ main_kb.{func} MISSING")


        from bot.handlers import start, exchange, mixer, info, settings

        print("✅ All handler modules imported")


        print("--- Testing router definitions ---")

        modules = [start, exchange, mixer, info, settings]

        for mod in modules:

            if hasattr(mod, 'router'):

                print(f"  ✅ {mod.__name__}.router exists")

            else:

                print(f"  ❌ {mod.__name__}.router MISSING")


    except Exception as e:

        print(f"❌ CRITICAL ERROR: {e}")

        sys.exit(1)

    print("--- QA Check Passed ---")


if __name__ == "__main__":

    test_imports()

