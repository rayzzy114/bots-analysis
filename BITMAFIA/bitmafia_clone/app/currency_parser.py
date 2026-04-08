from dataclasses import dataclass


@dataclass
class ParsedAmount:
    coin_symbol: str
    coin_amount: float
    amount_rub: float

class CurrencyParser:
    def __init__(self, settings_store):
        self.settings = settings_store

    def parse(self, coin_symbol: str, raw_input: str) -> ParsedAmount:
        # Simplified parsing logic for demonstration
        amount = float(raw_input)
        commission = self.settings.commission_percent
        amount_rub = amount * (1 + commission / 100) # Assuming some rate context
        return ParsedAmount(coin_symbol=coin_symbol, coin_amount=amount, amount_rub=amount_rub)
