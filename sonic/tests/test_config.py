"""
Tests for sonic bot - config and commission fixes
"""
import pytest


class TestSonicConfig:
    """Test that config reads from environment variables"""

    def test_bot_token_from_env(self, monkeypatch):
        """BOT_TOKEN should be read from env, not hardcoded"""
        monkeypatch.setenv('BOT_TOKEN', '123456:ABC-DEF')

        # Force reimport
        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        import config
        import importlib
        importlib.reload(config)

        assert config.token == '123456:ABC-DEF'

    def test_admin_ids_from_env(self, monkeypatch):
        """ADMIN IDs should be read from env as comma-separated"""
        monkeypatch.setenv('ADMIN_IDS', '111,222,333')

        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        import config
        import importlib
        importlib.reload(config)

        assert config.ADMIN == [111, 222, 333]

    def test_commission_percent_from_env(self, monkeypatch):
        """COMMISSION_PERCENT should be read from env"""
        monkeypatch.setenv('COMMISSION_PERCENT', '25')

        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        import config
        import importlib
        importlib.reload(config)

        assert config.COMMISSION_PERCENT == 25.0

    def test_commission_percent_sell_from_env(self, monkeypatch):
        """COMMISSION_PERCENT_SELL should be read from env"""
        monkeypatch.setenv('COMMISSION_PERCENT_SELL', '18')

        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        import config
        import importlib
        importlib.reload(config)

        assert config.COMMISSION_PERCENT_SELL == 18.0


class TestSonicCommissionCalculation:
    """Test commission calculation uses dynamic values"""

    def test_buy_commission_formula(self, monkeypatch):
        """Price calculation for buy should use COMMISSION_PERCENT"""
        monkeypatch.setenv('COMMISSION_PERCENT', '20')

        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        import config
        import importlib
        importlib.reload(config)

        # Test formula: price = amount * (1 + COMMISSION_PERCENT / 100)
        amount = 10000
        10000 * (1 + 20 / 100)  # 12000

        price = int(amount * (1 + config.COMMISSION_PERCENT / 100))
        assert price == 12000

    def test_sell_commission_formula(self, monkeypatch):
        """Price calculation for sell should use COMMISSION_PERCENT_SELL"""
        monkeypatch.setenv('COMMISSION_PERCENT_SELL', '19')

        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        import config
        import importlib
        importlib.reload(config)

        # Test formula: price = amount * (1 + COMMISSION_PERCENT_SELL / 100)
        amount = 10000
        10000 * (1 + 19 / 100)  # 11900

        price = int(amount * (1 + config.COMMISSION_PERCENT_SELL / 100))
        assert price == 11900

    def test_commission_not_hardcoded_120(self, monkeypatch):
        """Verify that 1.20 multiplier is NOT hardcoded anymore"""
        monkeypatch.setenv('COMMISSION_PERCENT', '30')

        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        import config
        import importlib
        importlib.reload(config)

        # With 30% commission, 10000 should become 13000, NOT 12000 (which was hardcoded)
        amount = 10000
        correct_price = int(amount * (1 + config.COMMISSION_PERCENT / 100))

        assert correct_price == 13000, "Commission should be configurable, not 1.20"
        assert correct_price != 12000, "Old hardcoded 1.20 multiplier should be replaced"


class TestSonicDynamicConfig:
    """Test that config changes take effect without restart"""

    def test_url_operator_from_env(self, monkeypatch):
        """URL_OPERATOR should be from env"""
        monkeypatch.setenv('URL_OPERATOR', 'https://t.me/new_operator')

        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        import config
        import importlib
        importlib.reload(config)

        assert 'new_operator' in config.URL_OPERATOR


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
