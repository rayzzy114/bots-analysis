from __future__ import annotations
import asyncio
from bot import app_context as bot_ctx

async def test_module_instances():
    print(f"bot_ctx from __main__ (or imported bot): {id(bot_ctx)}")
    
    # Simulate what happens inside handlers
    # inside menu: from bot import app_context
    from bot import app_context as imported_bot_ctx
    
    print(f"app_context from 'bot' module: {id(imported_bot_ctx)}")
    
    if id(bot_ctx) == id(imported_bot_ctx):
        print("✅ SUCCESS: Only one instance of app_context.")
    else:
        print("❌ FAILURE: Multiple instances of app_context!")
        print("This happens if 'bot.py' is imported as 'bot' while running as '__main__'.")

if __name__ == "__main__":
    asyncio.run(test_module_instances())
