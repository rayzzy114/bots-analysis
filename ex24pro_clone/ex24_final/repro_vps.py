from __future__ import annotations

import asyncio

from handlers.livechat import _get_link
from handlers.menu import _get_link_kwargs
from runtime_state import app_context


async def test():
    print('Current links:', await _get_link_kwargs())
    print('Link from livechat:', await _get_link('reviews'))

    # Simulate update like in admin panel
    new_val = 'https://t.me/REPRO_TEST_LINK_2'
    print(f'Updating reviews to {new_val}...')
    app_context.settings.set_link('reviews', new_val)

    print('Links after update:', await _get_link_kwargs())
    print('Link from livechat after update:', await _get_link('reviews'))

if __name__ == '__main__':
    asyncio.run(test())
