from fastapi import FastAPI, Request, HTTPException

from fastapi.responses import RedirectResponse

from sqladmin import Admin, ModelView

from sqladmin.authentication import AuthenticationBackend

from sqlalchemy import select

from core.database import engine, async_session, init_db

from core.models import User, Order, Rate, PaymentMethod, FileCache, Setting

from core.config import Config

from contextlib import asynccontextmanager

import logging


@asynccontextmanager

async def lifespan(app: FastAPI):

    try:

        await init_db()

        logging.info("Database initialized successfully.")

    except Exception as e:

        logging.error(f"Failed to initialize database: {e}")

    yield


class AdminAuth(AuthenticationBackend):

    async def login(self, request: Request) -> bool:

        form = await request.form()

        username = form.get("username")

        password = form.get("password")

        if username == Config.WEB_ADMIN_USERNAME and password == Config.WEB_ADMIN_PASSWORD:

            request.session.update({"token": Config.SECRET_KEY[:32]})

            return True

        return False


    async def logout(self, request: Request) -> bool:

        request.session.clear()

        return True


    async def authenticate(self, request: Request) -> bool:

        return "token" in request.session


app = FastAPI(title="Lucky Exchange Admin", lifespan=lifespan)

authentication_backend = AdminAuth(secret_key=Config.SECRET_KEY)

admin = Admin(

    app,

    engine,

    authentication_backend=authentication_backend,

    base_url="/admin",

    logo_url="https://img.icons8.com/color/48/clover.png"

)



class UserAdmin(ModelView, model=User):

    column_list = ["id", "telegram_id", "username", "balance"]

    column_default_sort = [("id", True)]

    column_formatters = {

        "balance": lambda m, a: f"{m.balance:,.2f} ₽"

    }

    name = "Пользователь"

    name_plural = "Пользователи"

    icon = "fa-solid fa-user"


class OrderAdmin(ModelView, model=Order):

    column_list = ["id", "type", "status", "amount_in", "currency_in", "created_at"]


    column_default_sort = [("id", True)]

    column_formatters = {

        "amount_in": lambda m, a: f"{m.amount_in:,.4f}"

    }

    name = "Заявка"

    name_plural = "Заявки"

    icon = "fa-solid fa-cart-shopping"


class RateAdmin(ModelView, model=Rate):

    column_list = ["currency", "buy_rate", "sell_rate"]

    name = "Курс"

    name_plural = "Курсы валют"

    icon = "fa-solid fa-chart-line"


class PaymentMethodAdmin(ModelView, model=PaymentMethod):

    column_list = ["name", "type", "is_active"]

    name = "Метод оплаты"

    name_plural = "Методы оплаты"

    icon = "fa-solid fa-credit-card"


class SettingAdmin(ModelView, model=Setting):

    column_list = ["key", "value"]

    name = "Настройка"

    name_plural = "Настройки (Реквизиты)"

    icon = "fa-solid fa-gear"


class FileCacheAdmin(ModelView, model=FileCache):

    column_list = ["key", "file_id"]

    name = "Кэш файла"

    name_plural = "Кэш медиа (File ID)"

    icon = "fa-solid fa-database"


admin.add_view(UserAdmin)

admin.add_view(OrderAdmin)

admin.add_view(RateAdmin)

admin.add_view(PaymentMethodAdmin)

admin.add_view(SettingAdmin)

admin.add_view(FileCacheAdmin)


@app.get("/")

async def root_redirect():

    return RedirectResponse(url="/admin")


@app.get("/health")

async def health_check():

    return {"status": "healthy"}


if __name__ == "__main__":

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
