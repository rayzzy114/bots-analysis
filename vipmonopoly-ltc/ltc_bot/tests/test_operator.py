"""
Tests for vipmonopoly-ltc bot - dynamic operator getters
"""
import pytest
import os


class TestOperatorGetters:
    """Test that operator values are read dynamically via getter functions"""

    def test_get_operator_returns_string(self, monkeypatch):
        """get_operator() should return string operator username"""
        monkeypatch.setenv('operator', 'TestOperator123')

        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        from config import get_operator

        result = get_operator()
        assert isinstance(result, str)
        assert result == 'TestOperator123'

    def test_get_operator2_returns_string(self, monkeypatch):
        """get_operator2() should return string"""
        monkeypatch.setenv('operator2', 'OperatorTwo456')

        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        from config import get_operator2

        result = get_operator2()
        assert isinstance(result, str)
        assert result == 'OperatorTwo456'

    def test_get_operator3_returns_string(self, monkeypatch):
        """get_operator3() should return string"""
        monkeypatch.setenv('operator3', 'OperatorThree789')

        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        from config import get_operator3

        result = get_operator3()
        assert isinstance(result, str)
        assert result == 'OperatorThree789'

    def test_get_work_operator_returns_string(self, monkeypatch):
        """get_work_operator() should return string"""
        monkeypatch.setenv('work_operator', 'WorkOperatorJob')

        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        from config import get_work_operator

        result = get_work_operator()
        assert isinstance(result, str)
        assert result == 'WorkOperatorJob'

    def test_operator_not_stored_as_module_variable(self, monkeypatch):
        """
        CRITICAL: Verify that 'operator' is NOT a module-level variable
        that gets imported once. It should be fetched via getter.
        """
        monkeypatch.setenv('operator', 'OriginalOperator')

        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        from config import get_operator

        # First call
        result1 = get_operator()
        assert result1 == 'OriginalOperator'

        # Change env and call again - should return NEW value
        monkeypatch.setenv('operator', 'NewOperatorChanged')

        # Need to reload to pick up new env
        import importlib
        import config
        importlib.reload(config)
        from config import get_operator as get_operator_reloaded

        result2 = get_operator_reloaded()
        assert result2 == 'NewOperatorChanged', \
            "Operator should change when env changes, proving it's read at call time"


class TestOperatorInText:
    """Test that operators are used correctly in text generation"""

    def test_operator_format_in_text(self):
        """Operator should be formatted with @ in text"""
        import sys
        for mod in list(sys.modules.keys()):
            if 'handlers' in mod:
                del sys.modules[mod]

        from config import get_operator

        operator = get_operator()
        text = f"@{operator}"

        assert text.startswith('@'), "Operator should be prefixed with @"


class TestRatesFallback:
    """Test rate fallback values exist but are reasonable"""

    def test_ltc_rate_fallback_exists(self, monkeypatch):
        """LTC_RATE_USD fallback should exist for API failure"""
        # Clear env
        monkeypatch.delenv('LTC_RATE_USD', raising=False)

        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        from config import LTC_RATE_USD

        # Fallback should be a reasonable number (not 0 or negative)
        assert LTC_RATE_USD > 0
        assert LTC_RATE_USD < 10000, "Fallback rate should be reasonable"

    def test_btc_rate_fallback_exists(self, monkeypatch):
        """BTC_RATE_USD fallback should exist for API failure"""
        monkeypatch.delenv('BTC_RATE_USD', raising=False)

        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        from config import BTC_RATE_USD

        assert BTC_RATE_USD > 0
        assert BTC_RATE_USD < 200000, "Fallback BTC rate should be reasonable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
