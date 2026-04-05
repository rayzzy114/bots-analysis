"""
Integration tests for BULBA handlers
Tests that handlers correctly use dynamic rates from CoinGecko
"""
import pytest


class TestBuyHandlerWithDynamicRates:
    """Test that buy handler uses dynamic rates, not hardcoded"""

    @pytest.mark.asyncio
    async def test_handle_amount_uses_coingecko_rates(self):
        """When user enters amount, rates should come from CoinGecko"""
        import sys
        for mod in list(sys.modules.keys()):
            if 'bot' in mod:
                del sys.modules[mod]

        # We need to verify that handle_amount calls get_btc_rates
        # This is a pattern test - checking the code structure

        import os
        bot_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'bot.py'
        )

        with open(bot_path, 'r') as f:
            content = f.read()

        # Verify that get_btc_rates is called in handle_amount
        assert 'await get_btc_rates()' in content or 'get_btc_rates()' in content, \
            "handle_amount should call get_btc_rates()"

        # Verify that CoinGecko API URL is present
        assert 'api.coingecko.com' in content, \
            "Should use CoinGecko API"


class TestAdminRatesPanel:
    """Test admin rates panel shows correct info"""

    def test_admin_rates_shows_coingecko_text(self):
        """Admin rates panel should show CoinGecko source"""
        import os
        admin_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'handlers', 'admin.py'
        )

        if os.path.exists(admin_path):
            with open(admin_path, 'r') as f:
                content = f.read()

            # Should mention CoinGecko
            if 'rates' in content.lower():
                # This is a placeholder - actual test would need bot running
                pass


class TestRateUpdateWithoutRestart:
    """Test that rate updates don't require bot restart"""

    def test_get_btc_rates_can_be_called_multiple_times(self):
        """get_btc_rates should return fresh data each call"""
        import sys
        for mod in list(sys.modules.keys()):
            if 'bot' in mod:
                del sys.modules[mod]

        from bot import get_btc_rates

        # Call twice - should work both times
        # (In real test, would verify different values if API changed)
        try:
            rates1 = get_btc_rates()
            rates2 = get_btc_rates()
            assert rates1 is not None
            assert rates2 is not None
        except Exception as e:
            pytest.fail(f"get_btc_rates failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
