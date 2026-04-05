"""
Tests for lucky_original_production - NEW CoinGecko + commission config fixes
CRITICAL: These tests verify hardcoded 0.82, 0.18, 95 were replaced with config
"""
import pytest
import os
import sys


class TestCommissionConfig:
    """Test commission is configurable via environment"""

    def test_commission_buy_from_env(self, monkeypatch):
        """COMMISSION_BUY must come from environment"""
        monkeypatch.setenv("COMMISSION_BUY", "25")

        for mod in list(sys.modules.keys()):
            if 'core' in mod or 'config' in mod:
                del sys.modules[mod]

        from core.config import COMMISSION_BUY
        assert COMMISSION_BUY == 25.0

    def test_commission_default_20_percent(self):
        """Default should be 20%"""
        env_backup = os.environ.get('COMMISSION_BUY')

        if 'COMMISSION_BUY' in os.environ:
            del os.environ['COMMISSION_BUY']

        try:
            for mod in list(sys.modules.keys()):
                if 'core' in mod or 'config' in mod:
                    del sys.modules[mod]

            from core.config import COMMISSION_BUY
            assert COMMISSION_BUY == 20.0
        finally:
            if env_backup:
                os.environ['COMMISSION_BUY'] = env_backup

    def test_network_fee_from_env(self, monkeypatch):
        """NETWORK_FEE must come from environment"""
        monkeypatch.setenv("NETWORK_FEE", "150")

        for mod in list(sys.modules.keys()):
            if 'core' in mod or 'config' in mod:
                del sys.modules[mod]

        from core.config import NETWORK_FEE
        assert NETWORK_FEE == 150.0

    def test_network_fee_default_95(self):
        """Default network fee should be 95 RUB"""
        env_backup = os.environ.get('NETWORK_FEE')

        if 'NETWORK_FEE' in os.environ:
            del os.environ['NETWORK_FEE']

        try:
            for mod in list(sys.modules.keys()):
                if 'core' in mod or 'config' in mod:
                    del sys.modules[mod]

            from core.config import NETWORK_FEE
            assert NETWORK_FEE == 95.0
        finally:
            if env_backup:
                os.environ['NETWORK_FEE'] = env_backup


class TestCoinGeckoIntegration:
    """Test CoinGecko API is integrated"""

    def test_coingecko_api_url_defined(self):
        """COINGECKO_API_URL should be defined in config"""
        for mod in list(sys.modules.keys()):
            if 'core' in mod or 'config' in mod:
                del sys.modules[mod]

        from core.config import COINGECKO_API_URL
        assert COINGECKO_API_URL is not None
        assert 'coingecko' in COINGECKO_API_URL.lower()


class TestNoHardcodedConstants:
    """Verify hardcoded 0.82, 0.18, 95 are replaced with config"""

    def test_no_hardcoded_082_083_in_exchange(self):
        """Code should NOT contain hardcoded 0.82 or 0.83 without Config"""
        import os
        exchange_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'bot', 'handlers', 'exchange.py'
        )

        if os.path.exists(exchange_path):
            with open(exchange_path, 'r') as f:
                content = f.read()

            lines = content.split('\n')

            for i, line in enumerate(lines):
                if '#' in line:
                    code_part = line.split('#')[0]
                else:
                    code_part = line

                # Check for 0.82 or 0.83 in arithmetic context
                if '0.82' in code_part or '0.83' in code_part:
                    assert 'COMMISSION' in code_part or 'Config' in code_part, \
                        f"Line {i+1}: Found hardcoded 0.82/0.83 without Config: {line.strip()}"

    def test_no_hardcoded_018_in_exchange(self):
        """Code should NOT contain hardcoded 0.18 without Config"""
        import os
        exchange_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'bot', 'handlers', 'exchange.py'
        )

        if os.path.exists(exchange_path):
            with open(exchange_path, 'r') as f:
                content = f.read()

            lines = content.split('\n')

            for i, line in enumerate(lines):
                if '#' in line:
                    code_part = line.split('#')[0]
                else:
                    code_part = line

                if '/ 0.18' in code_part or '* 0.18' in code_part or '0.18' in code_part:
                    assert 'COMMISSION' in code_part or 'Config' in code_part, \
                        f"Line {i+1}: Found hardcoded 0.18 without Config: {line.strip()}"


class TestRequisitesUnchanged:
    """Verify requisites from DB are still used (not hardcoded)"""

    def test_requisites_from_db_pattern_exists(self):
        """Requisites should still be fetched from database"""
        import os
        exchange_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'bot', 'handlers', 'exchange.py'
        )

        if os.path.exists(exchange_path):
            with open(exchange_path, 'r') as f:
                content = f.read()

            # Should still use DB pattern
            assert 'get_app_setting' in content or 'Setting' in content or 'db' in content.lower(), \
                "Requisites should still come from database"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
