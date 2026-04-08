from typing import NamedTuple, Optional
import re

class ParsedAmount(NamedTuple):
    amount: float
    currency: str
    is_valid: bool
    error: Optional[str] = None

class CurrencyParser:
    @staticmethod
    def parse(text: str) -> ParsedAmount:
        text = text.strip()
        match = re.match(r"([\d.,]+)\s*([a-zA-Z]+)", text)
        if not match:
            return ParsedAmount(0.0, "", False, "❌ Неверный формат суммы. Используйте: 100 BTC")
        
        amount_str = match.group(1).replace(",", ".")
        currency = match.group(2).upper()
        
        try:
            amount = float(amount_str)
            if amount <= 0:
                return ParsedAmount(0.0, currency, False, "⚠️ Сумма должна быть больше нуля")
            return ParsedAmount(amount, currency, True)
        except ValueError:
            return ParsedAmount(0.0, currency, False, "❌ Неверное числовое значение")
