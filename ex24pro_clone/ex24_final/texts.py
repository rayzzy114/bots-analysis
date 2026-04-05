from __future__ import annotations

TEXTS_RU: dict[str, str] = {
    "welcome_caption": (
        "✅ Ваша заявка № #{ticket_id} принята\n"
        "\n"
        "👩‍💻 Менеджер {manager_name} уже подключается к чату\n"
        "\n"
        "Уважаемые клиенты!\n"
        "В настоящее время в мире наблюдаются перебои в работе приложений Telegram и WhatsApp. \n"
        "Мы остаёмся на связи и готовы Вам помочь, но могут возникнуть задержки с ответами.\n"
        "\n"
        "Благодарим Вас за понимание и терпение. \n"
        "Мы ценим Ваше время и сделаем все возможное, чтобы оперативно ответить на ваши запросы.🤝\n"
        "\n"
        "➡️ Дополнительные способы связи:\n"
        "{link_support}"
    ),
    "welcome_source_question": "💛 Подскажите, пожалуйста, как вы узнали о боте?",
    "welcome_followup": "💛 Ответ принят! Спасибо за обратную связь!",
    "welcome_manager_connecting": "💛 Спасибо, менеджер уже подключается...",
    "welcome_manager_connecting_alt": "💛 Ожидайте, менеджер уже подключается...",
    "welcome_manager_connected": (
        "🧑‍💻Менеджер подключился к чату!\n"
        "\n"
        "Больше информации о нашем сервисе:\n"
        "\n"
        "⚡️EX24.PRO: Работаем в Таиланде, Китае, Бали, Турции и ОАЭ с 2015 года!\n"
        "\n"
        "🏠Новостной канал: <a href=\"https://t.me/exchange24thalland\">Ознакомиться</a>\n"
        "🫂Отзывы о работе: <a href=\"https://t.me/ex24pro_comments\">Ознакомиться</a>"
    ),
    "welcome_help_prompt": "💛 Здравствуйте, чем могу Вам помочь?",

    "offices": (
        "У нас 18 офисов 🏠, расположенных в различных городах. \n"
        "Каждый из них предлагает широкий спектр услуг и поддерживает качество работы "
        " на высшем уровне.\n"
        "\n"
        "Просмотрите всю контактную информацию, доступную по ссылке {link_offices}\n"
        "Будем рады видеть Вас в одном из наших филиалов!"
    ),

    "rates_th": (
        "Курсы Ex24 в Таиланде:\n"
        "\n"
        "🇷🇺 {rate_rub_thb} руб. = 1 бат\n"
        "💵 1 USDT = {rate_usdt_thb} бат\n"
        "\n"
        "📍 Более 30 направлений обмена, мы работаем быстро и без скрытых комиссий.\n"
        "\n"
        "🔹 Чем больше сумма обмена, тем выгоднее курс\n"
        "\n"
        "🌝 Обратите внимание: курс различается по дневным и ночным тарифам.\n"
        "\n"
        "Для какой суммы Вам сделать расчет?"
    ),

    "china_info": (
        "Мы помогаем:\n"
        "\n"
        "💸 Пополнять WeChat и Alipay\n"
        "📑 Оплачивать инвойсы и закупки у поставщиков\n"
        "🔄 Делать крупные переводы в Китай\n"
        "\n"
        "Быстро, надежно, по выгодному курсу."
    ),
    "china_rates": (
        "Курсы Ex24 в Китае:\n"
        "\n"
        "💵 1 USDT = {rate_usdt_cny} юаней\n"
        "🇷🇺 {rate_rub_cny} руб. = 1 юань\n"
        "\n"
        "📍 Более 30 направлений обмена, мы работаем быстро и без скрытых комиссий.\n"
        "\n"
        "🔹 Чем больше сумма обмена, тем выгоднее курс\n"
        "\n"
        "🌝 Обратите внимание: курс различается по дневным и ночным тарифам.\n"
        "\n"
        "Для какой суммы Вам сделать расчет?"
    ),
    "china_methods": (
        "Можем реализовать пополнение Wechat/Alipay/оплату инвойсов.\n"
        "Минимальная сумма - 1,000 CNY"
    ),

    "dubai_info": (
        "Мы помогаем в Дубае:\n"
        "\n"
        "💸 Обменивать рубли и онлайн USD на дирхамы\n"
        "🏦 Совершать переводы на счета в ОАЭ\n"
        "💳 Получать наличные в банкомате без карты\n"
        "🏡 Оплачивать недвижимость и аренду \n"
        "🌍 Отправлять крупные международные переводы\n"
        "📑Оплачивать инвойсы\n"
        "\n"
        "Работаем быстро и по выгодному курсу."
    ),
    "dubai_rates": (
        "Курсы Ex24 в Дубае:\n"
        "\n"
        "💵 1 USDT = {rate_usdt_aed} дирхам\n"
        "🇷🇺 {rate_rub_aed} руб. = 1 дирхам\n"
        "\n"
        "📍 Более 30 направлений обмена, мы работаем быстро и без скрытых комиссий.\n"
        "\n"
        "🔹 Чем больше сумма обмена, тем выгоднее курс\n"
        "\n"
        "🌝 Обратите внимание: курс различается по дневным и ночным тарифам.\n"
        "\n"
        "Для какой суммы Вам сделать расчет?"
    ),
    "dubai_methods": (
        "Доступные способы получения:\n"
        "-выдача ATM до 3 000 AED\n"
        "-перевод на счет/оплата инвойса\n"
        "-доставка курьером Дубай (стоимость 200 дирхам)"
    ),

    "bali_info": (
        "Мы помогаем на Бали:\n"
        "\n"
        "💸 Обменивать рубли и онлайн USD на рупии в любой точке острова\n"
        "🚚 Получать наличные доставкой\n"
        "🔄 Совершать переводы на индонезийские счета\n"
        "💳 Получать деньги в банкомате без карты\n"
        "🌍 Отправлять крупные международные переводы\n"
        "🏡 Оплачивать недвижимость и услуги застройщиков\n"
        "📑 Оплачивать инвойсы и закупки по всему миру\n"
        "\n"
        "Работаем быстро и по выгодному курсу."
    ),
    "bali_rates": (
        "Курсы Ex24 на Бали:\n"
        "\n"
        "💵 1 USDT = {rate_usdt_idr} рупий\n"
        "🇷🇺 1 рубль = {rate_rub_idr_inv} рупий\n"
        "\n"
        "📍 Более 30 направлений обмена, мы работаем быстро и без скрытых комиссий.\n"
        "\n"
        "🔹 Чем больше сумма обмена, тем выгоднее курс\n"
        "\n"
        "🌝 Обратите внимание: курс различается по дневным и ночным тарифам.\n"
        "\n"
        "Для какой суммы Вам сделать расчет?"
    ),
    "bali_methods": (
        "Можем предложить для Вас любой удобный вариант:\n"
        "\n"
        "- доставка курьером по адресу 🚚 (от 5.000.000 IDR )\n"
        "- выдача наличных рупий через банкоматы  (от 10.000 рублей до 3.000.000 IDR)\n"
        "- выплата на карту 💳 (от 10.000 рублей )\n"
        "\n"
        "Ближайший ATM Вы можете найти в Google Maps по названию банкомата."
    ),

    "lang_switched": "Русский язык успешно переключен.",

    "close_rating": (
        "Спасибо, что обратились к нам! Меня зовут {manager_name}, и я помогала вам сегодня. "
        "Пожалуйста, оцените качество обслуживания по шкале от 1 до 5 - это поможет нам стать лучше. "
        "Чтобы получить информацию о самых популярных мероприятиях на Пхукете , переходите по ссылке {link_tickets} "
        "Если у Вас есть другие вопросы, будем рады Вам помочь!"
    ),
    "close_bad_rating": (
        "Нам жаль, что Вы столкнулись с трудностями при обмене в нашем сервисе 😔\n"
        "Мы обязательно разберёмся в ситуации - Ваша заявка уже направлена в отдел контроля качества.\n"
        "Подскажите пожалуйста, что бы Вы хотели улучшить, как клиент?"
    ),
    "close_review": (
        "Спасибо, что выбрали Exchange 24 💛\n"
        "\n"
        "Ваш честный отзыв поможет стать нам лучше: {link_reviews}\n"
        "Это займет всего несколько минут."
    ),

    "livechat_forwarded": "📩 Клиент #{user_id} (@{username}):\n{text}",
    "livechat_photo": "📩 Клиент #{user_id} (@{username}) отправил фото",
    "livechat_document": "📩 Клиент #{user_id} (@{username}) отправил документ",
    "livechat_video": "📩 Клиент #{user_id} (@{username}) отправил видео",

    "turkey_info": (
        "Мы работаем в Турции:\n"
        "\n"
        "💸 Обмен рублей и онлайн USD на лиры\n"
        "🏡 Оплата недвижимости\n"
        "\n"
        "Быстро и по выгодному курсу."
    ),
    "turkey_rates": (
        "Курсы Ex24 в Турции:\n"
        "\n"
        "💵 1 USDT = {rate_usdt_try} лир\n"
        "🇷🇺 {rate_rub_try} рублей = 1 лира\n"
        "\n"
        "📍 Более 30 направлений обмена, работаем быстро и без скрытых комиссий.\n"
        "\n"
        "🔹 Чем больше сумма обмена, тем выгоднее курс.\n"
        "\n"
        "🌝 Обратите внимание: курс может отличаться в зависимости от дневного и ночного времени.\n"
        "\n"
        "Какую сумму хотите рассчитать?"
    ),
    "turkey_methods": (
        "Доступные способы получения:\n"
        "-Снятие в банкомате\n"
        "-Перевод на счёт / оплата счёта\n"
        "-Доставка курьером"
    ),
}

TEXTS_EN: dict[str, str] = {
    "welcome_caption": (
        "✅ Your request № #{ticket_id} has been accepted\n"
        "\n"
        "👩‍💻 Manager {manager_name} is connecting to the chat\n"
        "\n"
        "Dear clients!\n"
        "Currently, there are interruptions in Telegram and WhatsApp apps worldwide. \n"
        "We remain available and ready to help, but there may be delays in responses.\n"
        "\n"
        "Thank you for your understanding and patience. \n"
        "We value your time and will do our best to respond to your requests promptly.🤝\n"
        "\n"
        "➡️ Additional contact methods:\n"
        "{link_support}"
    ),
    "welcome_source_question": "💛 Could you please tell us how you heard about the bot?",
    "welcome_followup": "💛 Response received! Thank you for the feedback!",
    "welcome_manager_connecting": "💛 Thank you, a manager is already connecting...",
    "welcome_manager_connecting_alt": "💛 Please wait, a manager is already connecting...",
    "welcome_manager_connected": (
        "🧑‍💻Manager has connected to the chat!\n"
        "\n"
        "More information about our service:\n"
        "\n"
        "⚡️EX24.PRO: We work in Thailand, China, Bali, Turkey and the UAE since 2015!\n"
        "\n"
        "🏠News channel: <a href=\"https://t.me/exchange24thalland\">Open</a>\n"
        "🫂Reviews: <a href=\"https://t.me/ex24pro_comments\">Open</a>"
    ),
    "welcome_help_prompt": "Hello, how can I help you?",

    "turkey_info": (
        "We help in Turkey:\n"
        "\n"
        "💸 Exchange rubles and online USD to lira\n"
        "🏡 Pay for real estate\n"
        "\n"
        "Fast and at competitive rates."
    ),
    "turkey_rates": (
        "Ex24 rates in Turkey:\n"
        "\n"
        "💵 1 USDT = {rate_usdt_try} lira\n"
        "🇷🇺 {rate_rub_try} rubles = 1 lira\n"
        "\n"
        "📍 Over 30 exchange directions, we work quickly and without hidden fees.\n"
        "\n"
        "🔹 The larger the exchange amount, the better the rate.\n"
        "\n"
        "🌝 Please note: the rate varies depending on daytime and nighttime rates.\n"
        "\n"
        "What amount would you like to calculate?"
    ),
    "turkey_methods": (
        "Available payment methods:\n"
        "-ATM withdrawal\n"
        "-Transfer to account/invoice payment\n"
        "-Courier delivery"
    ),

    "rates_th": (
        "Ex24 rates in Thailand:\n"
        "\n"
        "🇷🇺 {rate_rub_thb} rubles = 1 baht\n"
        "💵 1 USDT = {rate_usdt_thb} baht\n"
        "\n"
        "📍 Over 30 exchange directions, we work quickly and without hidden fees.\n"
        "\n"
        "🔹 The larger the exchange amount, the better the rate.\n"
        "\n"
        "🌝 Please note: the rate varies depending on daytime and nighttime rates.\n"
        "\n"
        "What amount would you like to calculate?"
    ),

    "china_info": (
        "We help with:\n"
        "\n"
        "💸 WeChat and Alipay top-ups\n"
        "📑 Invoice and supplier payments\n"
        "🔄 Large transfers to China\n"
        "\n"
        "Fast, reliable, at competitive rates."
    ),
    "china_rates": (
        "Ex24 rates in China:\n"
        "\n"
        "💵 1 USDT = {rate_usdt_cny} yuan\n"
        "🇷🇺 {rate_rub_cny} rubles = 1 yuan\n"
        "\n"
        "📍 Over 30 exchange directions, we work quickly and without hidden fees.\n"
        "\n"
        "🔹 The larger the exchange amount, the better the rate.\n"
        "\n"
        "🌝 Please note: the rate varies depending on daytime and nighttime rates.\n"
        "\n"
        "What amount would you like to calculate?"
    ),
    "china_methods": (
        "We can facilitate Wechat/Alipay top-ups and invoice payments.\n"
        "Minimum amount - 1,000 CNY"
    ),

    "dubai_info": (
        "We help in Dubai:\n"
        "\n"
        "💸 Exchange rubles and online USD to dirhams\n"
        "🏦 Make transfers to UAE accounts\n"
        "💳 Get cash from ATMs without a card\n"
        "🏡 Pay for real estate and rent \n"
        "🌍 Send large international transfers\n"
        "📑 Pay invoices\n"
        "\n"
        "Fast and at competitive rates."
    ),
    "dubai_rates": (
        "Ex24 rates in Dubai:\n"
        "\n"
        "💵 1 USDT = {rate_usdt_aed} dirhams\n"
        "🇷🇺 {rate_rub_aed} rubles = 1 dirham\n"
        "\n"
        "📍 Over 30 exchange directions, we work quickly and without hidden fees.\n"
        "\n"
        "🔹 The larger the exchange amount, the better the rate.\n"
        "\n"
        "🌝 Please note: the rate varies depending on daytime and nighttime rates.\n"
        "\n"
        "What amount would you like to calculate?"
    ),
    "dubai_methods": (
        "Available payment methods:\n"
        "-ATM withdrawal up to 3,000 AED\n"
        "-Transfer to account/invoice payment\n"
        "-Courier delivery Dubai (cost 200 dirhams)"
    ),

    "bali_info": (
        "We help in Bali:\n"
        "\n"
        "💸 Exchange rubles and online USD to rupiah anywhere on the island\n"
        "🚚 Get cash delivered\n"
        "🔄 Make transfers to Indonesian accounts\n"
        "💳 Get money from ATMs without a card\n"
        "🌍 Send large international transfers\n"
        "🏡 Pay for real estate and developer services\n"
        "📑 Pay invoices and purchases worldwide\n"
        "\n"
        "Fast and at competitive rates."
    ),
    "bali_rates": (
        "Ex24 rates in Bali:\n"
        "\n"
        "💵 1 USDT = {rate_usdt_idr} rupiah\n"
        "🇷🇺 1 ruble = {rate_rub_idr_inv} rupiah\n"
        "\n"
        "📍 Over 30 exchange directions, we work quickly and without hidden fees.\n"
        "\n"
        "🔹 The larger the exchange amount, the better the rate.\n"
        "\n"
        "🌝 Please note: the rate varies depending on daytime and nighttime rates.\n"
        "\n"
        "What amount would you like to calculate?"
    ),
    "bali_methods": (
        "We can offer any convenient option:\n"
        "\n"
        "- Courier delivery to your address 🚚 (from 5,000,000 IDR)\n"
        "- Cash rupiah withdrawal via ATMs (from 10,000 rubles up to 3,000,000 IDR)\n"
        "- Card payment 💳 (from 10,000 rubles)\n"
        "\n"
        "You can find the nearest ATM in Google Maps by the ATM name."
    ),

    "lang_switched": "English language has been successfully switched.",

    "close_rating": (
        "Thank you for contacting us! My name is {manager_name}, and I was assisting you today. "
        "Please rate the quality of service on a scale from 1 to 5 - it will help us improve. "
        "To find out about the most popular events in Phuket, follow the link {link_tickets} "
        "If you have any other questions, we will be happy to help!"
    ),
    "close_bad_rating": (
        "We're sorry you had difficulties with our exchange service 😔\n"
        "We will definitely look into it - your request has been forwarded to the quality control department.\n"
        "Could you tell us what you would like us to improve?"
    ),
    "close_review": (
        "Thank you for choosing Exchange 24 💛\n"
        "\n"
        "Your honest review will help us improve: {link_reviews}\n"
        "It will only take a few minutes."
    ),

    "livechat_forwarded": "📩 Client #{user_id} (@{username}):\n{text}",
    "livechat_photo": "📩 Client #{user_id} (@{username}) sent a photo",
    "livechat_document": "📩 Client #{user_id} (@{username}) sent a document",
    "livechat_video": "📩 Client #{user_id} (@{username}) sent a video",
}

ALL_TEXTS: dict[str, dict[str, str]] = {
    "ru": TEXTS_RU,
    "en": TEXTS_EN,
}


def get_text(key: str, lang: str = "ru") -> str:
    texts = ALL_TEXTS.get(lang, TEXTS_RU)
    return texts.get(key, TEXTS_RU.get(key, ""))
