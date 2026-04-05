from utils.database import get_commission, get_bank_details
import requests
from typing import Optional
import time
import os

class ExchangeRateManager:
    def __init__(self):
        self.RATE_BTC_TO_RUB = float(os.getenv('FALLBACK_BTC_TO_RUB', '6900000'))
        self.RATE_XMR_TO_RUB = float(os.getenv('FALLBACK_XMR_TO_RUB', '250000'))
        self.last_update_time = 0
        self.update_interval = 60
        
        self.api_endpoints = {
            'binance': 'https://api.binance.com/api/v3/ticker/price',
            'coinbase': 'https://api.coinbase.com/v2/exchange-rates',
            'coingecko': 'https://api.coingecko.com/api/v3/simple/price'
        }
        
        self.update_exchange_rates()
    
    def get_btc_to_rub_rate(self) -> float:
        current_time = time.time()
        if current_time - self.last_update_time > self.update_interval:
            self.update_exchange_rates()
        return self.RATE_BTC_TO_RUB
    
    def get_xmr_to_rub_rate(self) -> float:
        current_time = time.time()
        if current_time - self.last_update_time > self.update_interval:
            self.update_exchange_rates()
        return self.RATE_XMR_TO_RUB
    
    def update_exchange_rates(self) -> bool:
        try:
            btc_usd = self._get_btc_usd_rate()
            usd_rub = self._get_usd_rub_rate()
            
            if btc_usd and usd_rub:
                self.RATE_BTC_TO_RUB = btc_usd * usd_rub
                print(f"BTC/RUB обновлен: {self.RATE_BTC_TO_RUB}")
            
            xmr_usd = self._get_xmr_usd_rate()
            if xmr_usd and usd_rub:
                self.RATE_XMR_TO_RUB = xmr_usd * usd_rub
                print(f"XMR/RUB обновлен: {self.RATE_XMR_TO_RUB}")
            
            self.last_update_time = time.time()
            return True
            
        except Exception as e:
            print(f"Ошибка обновления курсов: {e}")
            return False
    
    def _get_btc_usd_rate(self) -> Optional[float]:
        try:
            response = requests.get(
                f"{self.api_endpoints['binance']}?symbol=BTCUSDT",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return float(data.get('price', 0))
        except Exception as e:
            print(f"Binance BTC не доступен: {e}")

        try:
            response = requests.get(
                self.api_endpoints['coinbase'],
                params={'currency': 'USD'},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return float(data.get('data', {}).get('rates', {}).get('BTC', 0))
        except Exception as e:
            print(f"Coinbase BTC не доступен: {e}")

        try:
            response = requests.get(
                f"{self.api_endpoints['coingecko']}?ids=bitcoin&vs_currencies=usd",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('bitcoin', {}).get('usd', 0)
        except Exception as e:
            print(f"CoinGecko BTC не доступен: {e}")

        return None
    
    def _get_xmr_usd_rate(self) -> Optional[float]:
        try:
            response = requests.get(
                f"{self.api_endpoints['coingecko']}?ids=monero&vs_currencies=usd",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('monero', {}).get('usd', 0)
        except Exception as e:
            print(f"CoinGecko XMR не доступен: {e}")
        
        return None
    
    def _get_usd_rub_rate(self) -> Optional[float]:
        try:
            response = requests.get(
                'https://www.cbr-xml-daily.ru/daily_json.js',
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('Valute', {}).get('USD', {}).get('Value', 0)
        except Exception as e:
            print(f"ЦБ РФ не доступен: {e}")
        
        try:
            response = requests.get(
                f"{self.api_endpoints['binance']}?symbol=USDTRUB",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return float(data.get('price', 0))
        except Exception as e:
            print(f"Binance USDT/RUB не доступен: {e}")
        
        return None
    
    def get_all_rates(self) -> dict:
        return {
            'BTC_RUB': self.get_btc_to_rub_rate(),
            'XMR_RUB': self.get_xmr_to_rub_rate(),
            'last_update': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.last_update_time))
        }

rate_manager = ExchangeRateManager()

RATE_BTC_TO_RUB = rate_manager.get_btc_to_rub_rate()
RATE_XMR_TO_RUB = rate_manager.get_xmr_to_rub_rate()

def get_commission_rate():
    commission_from_env = os.getenv("COMMISSION")
    if commission_from_env is not None:
        try:
            return float(commission_from_env)
        except ValueError:
            pass
    return get_commission()

def get_bank_details_from_db():
    return get_bank_details()

BANK_DETAILS = get_bank_details_from_db()

def parse_amount(text: str) -> float:
    text = text.replace(" ", "")
    text = text.replace(",", ".")
    return float(text)

def is_rub_amount(amount: float) -> bool:
    return amount > 1000