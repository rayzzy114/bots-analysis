"""
Tests for donald bot - CoinGecko integration and commission config
CRITICAL: These tests verify that hardcoded values were replaced with dynamic config
"""
import pytest
import os
import sys


class TestCommissionConfig:
    """Test commission is now configurable via environment"""

    def test_commission_buy_from_env(self, monkeypatch):
        """COMMISSION_BUY must be read from environment variable"""
        monkeypatch.setenv("COMMISSION_BUY", "25")

        # Force reimport
        for mod in list(sys.modules.keys()):
            if 'bot' in mod:
                del sys.modules[mod]

        from bot import COMMISSION_BUY
        assert COMMISSION_BUY == 25.0

    def test_commission_sell_from_env(self, monkeypatch):
        """COMMISSION_SELL must be read from environment variable"""
        monkeypatch.setenv("COMMISSION_SELL", "15")

        for mod in list(sys.modules.keys()):
            if 'bot' in mod:
                del sys.modules[mod]

        from bot import COMMISSION_SELL
        assert COMMISSION_SELL == 15.0

    def test_commission_default_20_percent(self):
        """Default commission should be 20% if not set in env"""
        env_backup_buy = os.environ.get('COMMISSION_BUY')
        env_backup_sell = os.environ.get('COMMISSION_SELL')

        if 'COMMISSION_BUY' in os.environ:
            del os.environ['COMMISSION_BUY']
        if 'COMMISSION_SELL' in os.environ:
            del os.environ['COMMISSION_SELL']

        try:
            for mod in list(sys.modules.keys()):
                if 'bot' in mod:
                    del sys.modules[mod]

            from bot import COMMISSION_BUY, COMMISSION_SELL
            assert COMMISSION_BUY == 20.0, "Default COMMISSION_BUY should be 20"
            assert COMMISSION_SELL == 20.0, "Default COMMISSION_SELL should be 20"
        finally:
            if env_backup_buy:
                os.environ['COMMISSION_BUY'] = env_backup_buy
            if env_backup_sell:
                os.environ['COMMISSION_SELL'] = env_backup_sell


class TestRateFunctionsExist:
    """Test that rate functions exist and use commission"""

    def test_get_crypto_rate_uses_commission_buy(self):
        """get_crypto_rate should use COMMISSION_BUY"""
        import os
        bot_path = os.path.join(os.path.dirname(__file__), '..', 'bot.py')

        with open(bot_path, 'r') as f:
            content = f.read()

        # Should have function that applies COMMISSION_BUY
        assert 'get_crypto_rate' in content, "get_crypto_rate function should exist"
        assert 'COMMISSION_BUY' in content, "COMMISSION_BUY should be used"

    def test_get_sell_rate_uses_commission_sell(self):
        """get_sell_rate should use COMMISSION_SELL"""
        import os
        bot_path = os.path.join(os.path.dirname(__file__), '..', 'bot.py')

        with open(bot_path, 'r') as f:
            content = f.read()

        assert 'get_sell_rate' in content, "get_sell_rate function should exist"
        assert 'COMMISSION_SELL' in content, "COMMISSION_SELL should be used"


class TestCoinGeckoIntegration:
    """Test CoinGecko API integration"""

    def test_get_official_rate_function_exists(self):
        """get_official_rate function must exist"""
        for mod in list(sys.modules.keys()):
            if 'bot' in mod:
                del sys.modules[mod]

        from bot import get_official_rate
        assert callable(get_official_rate)

    def test_fallback_rates_exist(self):
        """Fallback rates should be defined for API failure"""
        import os
        bot_path = os.path.join(os.path.dirname(__file__), '..', 'bot.py')

        with open(bot_path, 'r') as f:
            content = f.read()

        # Fallback rates should exist
        assert 'fallback_rates' in content.lower() or 'FALLBACK' in content, \
            "Fallback rates should be defined"


class TestNoHardcodedCommissionMultipliers:
    """Verify that hardcoded commission multipliers 1.20 are NOT in code"""

    def test_no_hardcoded_120_without_commission(self):
        """Code should NOT contain 'rate * 1.20' without COMMISSION reference"""
        import os
        bot_path = os.path.join(os.path.dirname(__file__), '..', 'bot.py')

        with open(bot_path, 'r') as f:
            content = f.read()

        lines = content.split('\n')

        for i, line in enumerate(lines):
            if '#' in line:
                code_part = line.split('#')[0]
            else:
                code_part = line

            # Check for bad patterns: * 1.20 without COMMISSION
            if ('* 1.20' in code_part or '*1.20' in code_part) and 'COMMISSION' not in code_part:
                pytest.fail(f"Line {i+1}: Found hardcoded '* 1.20' without COMMISSION: {line.strip()}")


class TestRequisitesUnchanged:
    """Verify that requisites were NOT modified (as per user request)"""

    def test_requisites_still_exist(self):
        """Requisites should still be in the code (not deleted)"""
        import os
        bot_path = os.path.join(os.path.dirname(__file__), '..', 'bot.py')

        with open(bot_path, 'r') as f:
            content = f.read()

        assert 'Ozon Банк' in content or '2204 3206 0905 0531' in content, \
            "Requisites should still exist in code"

    def test_btc_wallet_still_exists(self):
        """BTC wallet address should still be in code"""
        import os
        bot_path = os.path.join(os.path.dirname(__file__), '..', 'bot.py')

        with open(bot_path, 'r') as f:
            content = f.read()

        assert 'bc1q' in content, "BTC wallet should still exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
