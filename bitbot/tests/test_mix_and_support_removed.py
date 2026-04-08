from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_main_menu_has_no_mix_button() -> None:
    keyboards_source = _read("app/keyboards.py")
    assert 'KeyboardButton(text="MIX")' not in keyboards_source


def test_flow_has_no_mix_route_and_support_tag() -> None:
    flow_source = _read("app/handlers/flow.py")
    assert 'F.text == "MIX"' not in flow_source
    assert "@support" not in flow_source
