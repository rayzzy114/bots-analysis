import os

token = os.getenv('BOT_TOKEN', '8541487109:AAE-eud6dSDdRDx5kCPm5hO4zzfwyW_EEqQ')  # Токен бота
ADMIN = [int(x) for x in os.getenv('ADMIN_IDS', '8584904538').split(',')]  # Айди админов через запятую

URL_INFO = os.getenv('URL_INFO', 'https://telegra.ph/Pravila-i-soglashenie--Sonic-Ex-10-12')
OPERATOR_PAY = os.getenv('OPERATOR_PAY', '@rusadmln_16')  # @Username Оператора во время оплаты
URL_OPERATOR = os.getenv('URL_OPERATOR', 'https://t.me/rusadmln_16')  # Ссылка на оператора

BTC_WALLET = os.getenv('BTC_WALLET', 'bc1qm3aeqqe4mqg4gh672erqkgxrrqzjsejg7h0kqd')  # Адрес BTC
LTC_WALLET = os.getenv('LTC_WALLET', 'ltc1q56sj9ywwjykca6weh5e5kvx87gxuejkyldw00a')  # Адрес LTC
USERNAME_BOT = os.getenv('USERNAME_BOT', 'sonixekx_bot')  # Username бот без @
URL_SELL = os.getenv('URL_SELL', 'https://t.me/rusadmln_16')  # Ссылка на аккаунт для ПРОДАЖИ КРИПТЫ
URL_REWIEV = os.getenv('URL_REWIEV', 'https://t.me/Sonic_Ex_book')  # Ссылка на отзывы

# Комиссия бота (в процентах)
COMMISSION_PERCENT = float(os.getenv('COMMISSION_PERCENT', '20'))  # Наценка при покупке
COMMISSION_PERCENT_SELL = float(os.getenv('COMMISSION_PERCENT_SELL', '19'))  # Наценка при продаже/калькуляторе
