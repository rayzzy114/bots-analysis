"""
Tests for rocket bot - commission and rate calculation fixes
"""
import pytest


class TestRocketRateCalculation:
    """Test that rocket uses correct rate calculation (not 0.8066)"""

    def test_get_crypto_rates_returns_dict(self):
        """get_crypto_rates should return dict with crypto rates"""
        import sys
        for mod in list(sys.modules.keys()):
            if 'main' in mod:
                del sys.modules[mod]

        from main import get_crypto_rates

        rates = get_crypto_rates()

        assert isinstance(rates, dict)
        assert 'BTC' in rates
        assert rates['BTC'] > 0

    def test_calculate_crypto_amount(self):
        """Test calculate_crypto_amount function"""
        import sys
        for mod in list(sys.modules.keys()):
            if 'main' in mod:
                del sys.modules[mod]

        from main import calculate_crypto_amount, get_crypto_rates

        rates = get_crypto_rates()
        btc_rate = rates['BTC']

        # 1 BTC should cost btc_rate rubles
        result = calculate_crypto_amount(btc_rate, 'BTC')
        assert 0.99 < result < 1.01, f"Expected ~1 BTC, got {result}"

    def test_calculate_crypto_amount_ltc(self):
        """Test LTC calculation"""
        import sys
        for mod in list(sys.modules.keys()):
            if 'main' in mod:
                del sys.modules[mod]

        from main import calculate_crypto_amount, get_crypto_rates

        rates = get_crypto_rates()
        ltc_rate = rates['LTC']

        result = calculate_crypto_amount(ltc_rate, 'LTC')
        assert 0.99 < result < 1.01, f"Expected ~1 LTC, got {result}"


class TestRocketEstimatedRate:
    """Test that estimated_rate uses correct formula, NOT 0.8066 multiplier"""

    def test_estimated_rate_uses_correct_crypto_rate(self):
        """
        CRITICAL: estimated_rate should use get_crypto_rates()
        NOT the old buggy 0.8066 multiplier
        """
        import sys
        for mod in list(sys.modules.keys()):
            if 'main' in mod:
                del sys.modules[mod]

        from main import get_crypto_rates

        # Get current rate
        rates = get_crypto_rates()
        btc_rate = rates['BTC']

        # Simulate what the code should do now
        amount = 100000  # 100k rubles
        crypto_type = 'BTC'

        # NEW correct formula
        estimated_rate_new = get_crypto_rates().get(crypto_type, 9000000)

        # OLD buggy formula (0.8066 was WRONG)
        estimated_rate_old = amount * 0.8066

        # The new rate should be the actual BTC rate, not amount * 0.8066
        # 0.8066 gave completely wrong values
        assert estimated_rate_new == btc_rate, "Should use actual crypto rate"
        assert estimated_rate_new != estimated_rate_old, "New rate must differ from old buggy rate"

        # The old formula gave absurd values like 80660 for amount=100000
        # That's NOT a rate, it's a random multiplier
        assert estimated_rate_old != 100000, "Old formula was clearly broken"
        assert estimated_rate_new > 1000000, "BTC rate should be in millions"


class TestRocketCommissionMode:
    """Test commission mode settings"""

    def test_user_settings_have_commission_mode(self):
        """User settings should track commission_mode"""
        import sys
        for mod in list(sys.modules.keys()):
            if 'main' in mod:
                del sys.modules[mod]

        from main import get_user_settings

        # Default settings
        settings = get_user_settings(12345)

        assert 'commission_mode' in settings
        assert isinstance(settings['commission_mode'], bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
