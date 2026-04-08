"""
Integration tests for vipmonopoly-ltc handlers
Tests that handlers correctly use dynamic operator getters
"""
import os

import pytest


class TestHandlerImports:
    """Verify handlers import getter functions, not static variables"""

    def test_buy_handler_imports_getters(self):
        """buy.py should import get_operator functions, not static operator"""
        buy_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'handlers', 'buy.py'
        )

        with open(buy_path) as f:
            content = f.read()

        # Should import getter functions
        assert 'get_operator' in content, \
            "buy.py should import get_operator function"
        assert 'from config import' in content, \
            "Should import from config"

        # Should NOT import static operator
        assert 'from config import operator,' not in content, \
            "Should NOT import static operator variable"
        assert 'import operator' not in content, \
            "operator should not be imported as static variable"

    def test_start_handler_imports_getters(self):
        """start.py should use get_operator function"""
        start_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'handlers', 'start.py'
        )

        with open(start_path) as f:
            content = f.read()

        assert 'get_operator' in content, \
            "start.py should use get_operator()"
        assert 'get_work_operator' in content, \
            "start.py should use get_work_operator()"

    def test_promo_handler_imports_getters(self):
        """promo.py should use operator getter functions"""
        promo_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'handlers', 'promo.py'
        )

        if os.path.exists(promo_path):
            with open(promo_path) as f:
                content = f.read()

            assert 'get_operator' in content, \
                "promo.py should use get_operator()"

    def test_work_handler_imports_getters(self):
        """work.py should use work_operator getter"""
        work_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'handlers', 'work.py'
        )

        if os.path.exists(work_path):
            with open(work_path) as f:
                content = f.read()

            assert 'get_work_operator' in content, \
                "work.py should use get_work_operator()"


class TestOperatorInMessages:
    """Test that operator appears correctly in messages"""

    def test_operator_called_as_function(self):
        """Operator should be called as get_operator(), not used directly"""
        import os

        handler_files = [
            'handlers/buy.py',
            'handlers/start.py',
            'handlers/promo.py',
            'handlers/work.py',
        ]

        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        for handler_file in handler_files:
            path = os.path.join(base_path, handler_file)
            if os.path.exists(path):
                with open(path) as f:
                    content = f.read()

                # If get_operator is used, it should be called as function
                if 'get_operator' in content:
                    assert 'get_operator()' in content, \
                        f"{handler_file}: get_operator should be called as function"


class TestConfigReload:
    """Test that config reload mechanism works"""

    def test_reload_env_function_exists(self):
        """reload_env function should exist in config"""
        import sys
        for mod in list(sys.modules.keys()):
            if 'config' in mod:
                del sys.modules[mod]

        from config import reload_env

        assert callable(reload_env), "reload_env should be callable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
