from aiogram import Router
from handlers import start, buy_btc, pay_with_, buy_xmr, buy_base, admin, sell_btc_xmr, cabinet, daily_bonus, support, faq, none

def get_routers() -> list[Router]:
    return [
        start.router,
        admin.router,
        daily_bonus.router,
        support.router,
        faq.router,
        buy_btc.router,
        buy_xmr.router,
        cabinet.router,
        sell_btc_xmr.router,

        pay_with_.router,
        buy_base.router,

        none.router
    ]