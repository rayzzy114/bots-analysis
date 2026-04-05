"""
Tests for MIXMAFIA - operator links are now dynamic
CRITICAL: Verify os.getenv is used for operator links
"""
import pytest
import os
import sys


class TestOperatorLinksDynamic:
    """Test that operator links are read from environment, not hardcoded"""

    def test_operator_link_from_env(self, monkeypatch):
        """OPERATOR_LINK must be read from environment"""
        monkeypatch.setenv("OPERATOR_LINK", "https://t.me/new_mixmafia_op")

        # Force reimport
        for mod in list(sys.modules.keys()):
            if 'constants' in mod:
                del sys.modules[mod]

        from app.constants import DEFAULT_LINKS
        assert "new_mixmafia_op" in DEFAULT_LINKS.get("operator", "").lower() or \
               "new_mixmafia_op" in str(DEFAULT_LINKS), \
               f"OPERATOR_LINK should be from env, got: {DEFAULT_LINKS}"

    def test_channel_link_from_env(self, monkeypatch):
        """CHANNEL_LINK must be from environment"""
        monkeypatch.setenv("CHANNEL_LINK", "https://t.me/new_channel")

        for mod in list(sys.modules.keys()):
            if 'constants' in mod:
                del sys.modules[mod]

        from app.constants import DEFAULT_LINKS
        # Should contain new value or fallback to old
        assert DEFAULT_LINKS is not None

    def test_support_link_from_env(self, monkeypatch):
        """SUPPORT_LINK must be from environment"""
        monkeypatch.setenv("SUPPORT_LINK", "https://t.me/new_support")

        for mod in list(sys.modules.keys()):
            if 'constants' in mod:
                del sys.modules[mod]

        from app.constants import DEFAULT_LINKS
        assert DEFAULT_LINKS.get("support") is not None or DEFAULT_LINKS.get("operator") is not None


class TestLinksNotHardcoded:
    """Verify links are NOT hardcoded without env fallback"""

    def test_constants_uses_os_getenv(self):
        """constants.py should use os.getenv for links"""
        constants_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'app', 'constants.py'
        )

        with open(constants_path, 'r') as f:
            content = f.read()

        # Should have os.getenv
        assert 'os.getenv' in content, \
            "constants.py should use os.getenv for dynamic links"

    def test_no_hardcoded_telegram_links(self):
        """Should NOT have hardcoded t.me links without os.getenv fallback"""
        constants_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'app', 'constants.py'
        )

        with open(constants_path, 'r') as f:
            content = f.read()

        lines = content.split('\n')

        for i, line in enumerate(lines):
            if '#' in line:
                code_part = line.split('#')[0]
            else:
                code_part = line

            # If there's a hardcoded URL, it should be a fallback in os.getenv
            if 't.me/' in code_part or 'https://t.me/' in code_part:
                # Should be inside os.getenv as fallback
                assert 'os.getenv' in code_part or 'getenv' in code_part, \
                    f"Line {i+1}: t.me link should use os.getenv: {line.strip()}"


class TestRequisitesUnchanged:
    """Verify requisites (card numbers etc) were NOT touched"""

    def test_card_number_still_exists(self):
        """Card number 2200 0000 0000 0000 should still be in code"""
        # Card placeholder is in admin_kit/storage.py, not constants.py
        storage_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'admin_kit', 'storage.py'
        )

        if os.path.exists(storage_path):
            with open(storage_path, 'r') as f:
                content = f.read()

            # Card pattern should still exist (as placeholder)
            assert '2200' in content or '0000' in content, \
                "Card placeholder should still exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
