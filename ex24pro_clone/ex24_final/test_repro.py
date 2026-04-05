from __future__ import annotations
import asyncio
from bot import app_context as bot_ctx
from handlers.menu import _get_link_kwargs

async def test_link_update_consistency():
    print("Starting link update consistency test...")
    
    # 1. Check if we can get app_context from handlers
    
    # We need to see what app_context they are using.
    # Since they import it inside functions, we'll check it there.
    
    async def get_menu_ctx():
        from bot import app_context
        return app_context
        
    menu_ctx = await get_menu_ctx()
    print(f"bot_ctx id: {id(bot_ctx)}")
    print(f"menu_ctx id: {id(menu_ctx)}")
    
    if id(bot_ctx) == id(menu_ctx):
        print("✅ SUCCESS: app_context is the same.")
    else:
        print("❌ FAILURE: app_context is DIFFERENT.")
    
    # 2. Test update
    new_link = "https://t.me/test_update"
    print(f"Updating 'reviews' to {new_link}")
    bot_ctx.settings.set_link("reviews", new_link)
    
    links = await _get_link_kwargs()
    print(f"Menu links after update: {links}")
    
    if links["link_reviews"] == new_link:
        print("✅ SUCCESS: Link updated in menu kwargs.")
    else:
        print("❌ FAILURE: Link NOT updated in menu kwargs.")

if __name__ == "__main__":
    asyncio.run(test_link_update_consistency())
