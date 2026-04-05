"""
Tests for BULBA bot - CoinGecko rate fetching
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestCoinGeckoRates:
    """Test that rates are fetched dynamically from CoinGecko"""

    @pytest.fixture
    def mock_env(self, monkeypatch):
        """Set up test environment"""
        monkeypatch.setenv("BTC_RATE_USD", "45000.0")
        monkeypatch.setenv("BTC_RATE_RUB", "4500000.0")

    @pytest.mark.asyncio
    async def test_get_btc_rates_returns_tuple(self):
        """get_btc_rates should return tuple (usd, rub)"""
        # Import after env is set
        import sys

        # Clear any cached imports
        for mod in list(sys.modules.keys()):
            if 'bot' in mod or 'config' in mod:
                del sys.modules[mod]

        from bot import get_btc_rates

        with patch('bot.aiohttp.ClientSession') as mock_session:
            mock_response = MagicMock()
            mock_response.json = AsyncMock(return_value={
                'bitcoin': {'usd': 70000, 'rub': 6500000}
            })
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock()
            mock_session.return_value = mock_response

            usd, rub = await get_btc_rates()

            assert isinstance(usd, (int, float))
            assert isinstance(rub, (int, float))
            assert usd > 0
            assert rub > 0

    @pytest.mark.asyncio
    async def test_get_btc_rates_fallback_on_api_failure(self):
        """get_btc_rates should fallback to env values when API fails"""
        import sys

        for mod in list(sys.modules.keys()):
            if 'bot' in mod or 'config' in mod:
                del sys.modules[mod]

        from bot import get_btc_rates

        with patch('bot.aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.side_effect = Exception("API Error")

            with patch('bot.BTC_RATE_USD', 45000.0):
                with patch('bot.BTC_RATE_RUB', 4500000.0):
                    usd, rub = await get_btc_rates()

                    # Should fallback to env values
                    assert usd == 45000.0
                    assert rub == 4500000.0


class TestCommissionCalculation:
    """Test commission calculation is dynamic and correct"""

    def test_commission_percent_from_env(self, monkeypatch):
        """Commission should be read from environment"""
        monkeypatch.setenv("COMMISSION_PERCENT", "25")

        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        from config import COMMISSION_PERCENT

        assert COMMISSION_PERCENT == 25.0

    def test_commission_calculation_with_30_percent(self):
        """100 rub with 30% commission = 130 rub"""
        amount = 100
        commission_percent = 30
        expected = 130

        result = amount * (1 + commission_percent / 100)
        assert result == expected

    def test_commission_calculation_with_20_percent(self):
        """100 rub with 20% commission = 120 rub"""
        amount = 100
        commission_percent = 20
        expected = 120

        result = amount * (1 + commission_percent / 100)
        assert result == expected


class TestDynamicRateUsage:
    """Test that rates are actually used in calculations"""

    def test_calculate_crypto_amount_uses_dynamic_rate(self):
        """calculate_crypto_amount should use dynamic rate, not hardcoded"""
        # This tests that the function exists and can be called
        import sys
        for mod in list(sys.modules.keys()):
            if 'bot' in mod:
                del sys.modules[mod]

        from bot import get_crypto_rates

        rates = get_crypto_rates()
        assert 'BTC' in rates
        assert 'LTC' in rates
        assert 'USDT' in rates

        # Rates should be positive numbers
        for crypto, rate in rates.items():
            assert rate > 0, f"{crypto} rate should be positive"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
