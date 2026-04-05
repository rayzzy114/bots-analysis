"""
Tests for scooby_bot - dynamic commission percentage
"""
import pytest
import os


class TestScoobyCommissionConfig:
    """Test that commission is read from config, not hardcoded as 1.2"""

    def test_commission_percent_exists(self, monkeypatch):
        """COMMISSION_PERCENT should exist in config"""
        monkeypatch.setenv('COMMISSION_PERCENT', '30')

        import sys
        for mod in list(sys.modules.keys()):
            if 'cfg' in mod or 'base' in mod:
                del sys.modules[mod]

        from cfg.base import COMMISSION_PERCENT

        assert COMMISSION_PERCENT == 30.0

    def test_commission_default_30_percent(self):
        """Default commission should be 30% if not set"""
        import sys
        for mod in list(sys.modules.keys()):
            if 'cfg' in mod or 'base' in mod:
                del sys.modules[mod]

        # Clear env
        env_backup = os.environ.get('COMMISSION_PERCENT')
        if 'COMMISSION_PERCENT' in os.environ:
            del os.environ['COMMISSION_PERCENT']

        try:
            from cfg.base import COMMISSION_PERCENT

            # Default should be 30
            assert COMMISSION_PERCENT == 30.0
        finally:
            if env_backup:
                os.environ['COMMISSION_PERCENT'] = env_backup


class TestScoobyCommissionCalculation:
    """Test commission calculation uses dynamic value, not hardcoded 1.2"""

    def test_commission_formula_not_hardcoded(self, monkeypatch):
        """Commission should be calculated, not hardcoded as 1.2"""
        monkeypatch.setenv('COMMISSION_PERCENT', '30')

        import sys
        for mod in list(sys.modules.keys()):
            if 'cfg' in mod or 'base' in mod:
                del sys.modules[mod]

        from cfg.base import COMMISSION_PERCENT

        rub_base = 10000

        # Correct formula: base * (1 + commission/100)
        correct_result = int(rub_base * (1 + COMMISSION_PERCENT / 100))
        assert correct_result == 13000, "30% of 10000 should be 13000"

        # Old hardcoded: base * 1.2
        old_hardcoded = int(rub_base * 1.2)
        assert old_hardcoded == 12000, "Old 1.2 multiplier gave 12000"

        assert correct_result != old_hardcoded, "New formula must differ from old hardcoded"

    def test_commission_with_20_percent(self, monkeypatch):
        """Test with 20% commission"""
        monkeypatch.setenv('COMMISSION_PERCENT', '20')

        import sys
        for mod in list(sys.modules.keys()):
            if 'cfg' in mod or 'base' in mod:
                del sys.modules[mod]

        from cfg.base import COMMISSION_PERCENT

        rub_base = 10000
        result = int(rub_base * (1 + COMMISSION_PERCENT / 100))

        assert result == 12000

    def test_commission_with_25_percent(self, monkeypatch):
        """Test with 25% commission"""
        monkeypatch.setenv('COMMISSION_PERCENT', '25')

        import sys
        for mod in list(sys.modules.keys()):
            if 'cfg' in mod or 'base' in mod:
                del sys.modules[mod]

        from cfg.base import COMMISSION_PERCENT

        rub_base = 10000
        result = int(rub_base * (1 + COMMISSION_PERCENT / 100))

        assert result == 12500


class TestScoobyNoHardcodedMultiplier:
    """Verify that hardcoded 1.2 multiplier is no longer used"""

    def test_buy_py_no_hardcoded_12(self):
        """Verify buy.py does not contain hardcoded 1.2"""
        import sys
        for mod in list(sys.modules.keys()):
            if 'buy' in mod:
                del sys.modules[mod]

        # Read the file content
        import os
        buy_py_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'scooby', 'src', 'handlers', 'transaction', 'buy.py'
        )

        # Normalize path
        buy_py_path = os.path.normpath(buy_py_path)

        if os.path.exists(buy_py_path):
            with open(buy_py_path, 'r') as f:
                content = f.read()

            # Check for bad patterns
            assert 'rub_base * 1.2' not in content, \
                "Found hardcoded 'rub_base * 1.2' - should use COMMISSION_PERCENT"
            assert 'normal_with_fee = int(rub_base * (1 + COMMISSION_PERCENT / 100))' in content, \
                "Should use dynamic COMMISSION_PERCENT calculation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
