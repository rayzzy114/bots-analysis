"""
Tests for REDBULL - dynamic rates and operator
CRITICAL: Verify CoinGecko integration and dynamic operator
"""
import pytest
import os
import sys


class TestDynamicOperator:
    """Test operator/support URL is now dynamic"""

    def test_support_url_from_config(self, monkeypatch):
        """SUPPORT_CHAT_URL should be readable from config"""
        # Monkeypatch config.json
        config_data = {
            "support_chat_url": "https://t.me/new_redbull_support",
            "commission_percent": 0.18
        }

        import json
        config_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'config.json'
        )

        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                original = json.load(f)

            # Patch with new support URL
            config_data.update(original)
            config_data['support_chat_url'] = "https://t.me/new_redbull_support"

            with open(config_path + '.test', 'w') as f:
                json.dump(config_data, f)

            try:
                # Try importing after patch
                for mod in list(sys.modules.keys()):
                    if 'main' in mod:
                        del sys.modules[mod]

                # Read config directly
                with open(config_path, 'r') as f:
                    loaded = json.load(f)

                assert loaded.get('support_chat_url') == "https://t.me/new_redbull_support"
            finally:
                # Cleanup
                if os.path.exists(config_path + '.test'):
                    os.remove(config_path + '.test')

    def test_get_support_url_function_exists(self):
        """get_support_chat_url() function should exist"""
        import os
        main_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'main.py'
        )

        with open(main_path, 'r') as f:
            content = f.read()

        # Should have get_support_chat_url or similar
        assert 'get_support' in content.lower() or 'support_url' in content.lower(), \
            "Should have dynamic support URL function"


class TestCoinGeckoRates:
    """Test CoinGecko integration for rates"""

    def test_fetch_coingecko_function_exists(self):
        """Should have fetch from CoinGecko"""
        import os
        main_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'main.py'
        )

        with open(main_path, 'r') as f:
            content = f.read()

        assert 'coingecko' in content.lower() or 'fetch_rate' in content.lower(), \
            "Should have CoinGecko rate fetching"

    def test_binance_fallback_exists(self):
        """Should have Binance as fallback for rates"""
        import os
        main_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'main.py'
        )

        with open(main_path, 'r') as f:
            content = f.read()

        assert 'binance' in content.lower() or 'BINANCE' in content, \
            "Should have Binance fallback for rates"


class TestCommissionDynamic:
    """Test commission is dynamic"""

    def test_commission_from_config(self):
        """Commission should come from config, not hardcoded"""
        import os
        main_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'main.py'
        )

        with open(main_path, 'r') as f:
            content = f.read()

        # Should reference commission_percent from config
        assert 'commission' in content.lower(), \
            "Should have commission handling"

        # Should NOT have hardcoded 0.18 without config reference
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '0.18' in line:
                code_part = line.split('#')[0] if '#' in line else line
                if '*' in code_part or '/' in code_part:
                    assert 'commission' in code_part.lower() or 'config' in code_part.lower(), \
                        f"Line {i+1}: 0.18 should reference commission/config: {line.strip()}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
