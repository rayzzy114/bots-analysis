import ast
import json
from pathlib import Path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def collect_string_literals(py_file: Path) -> set[str]:
    module = ast.parse(read_text(py_file), filename=str(py_file))
    literals: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.add(node.value)
    return literals


def collect_all_literals(project_root: Path) -> set[str]:
    literals: set[str] = set()
    for py_file in (project_root / "app").rglob("*.py"):
        literals.update(collect_string_literals(py_file))
    literals.update(collect_string_literals(project_root / "main.py"))
    return literals


def normalize(s: str) -> str:
    return "\n".join(line.rstrip() for line in s.strip().splitlines())


def run() -> int:
    project_root = Path(__file__).resolve().parents[1]
    donor_bundle = project_root.parent / "output" / "donor_bot" / "bundle.json"
    if not donor_bundle.exists():
        print(f"ERROR: donor bundle not found: {donor_bundle}")
        return 2

    bundle = json.loads(read_text(donor_bundle))
    donor_states = bundle.get("states", {})
    donor_buttons = {
        button.get("text", "")
        for state in donor_states.values()
        for button in state.get("buttons", [])
        if button.get("text", "")
    }
    donor_texts = {
        normalize(state.get("text", ""))
        for state in donor_states.values()
        if state.get("text", "").strip()
    }

    literals = collect_all_literals(project_root)
    literal_norm = {normalize(item) for item in literals if item.strip()}

    missing_buttons = sorted(btn for btn in donor_buttons if btn not in literals)
    matched_texts = sum(1 for t in donor_texts if t in literal_norm)
    missing_texts = sorted(t for t in donor_texts if t not in literal_norm)

    report = {
        "donor_states": len(donor_states),
        "donor_buttons": len(donor_buttons),
        "donor_text_nodes": len(donor_texts),
        "matched_text_nodes": matched_texts,
        "missing_text_nodes": len(missing_texts),
        "missing_buttons_count": len(missing_buttons),
        "missing_buttons": missing_buttons,
        "missing_text_examples": missing_texts[:12],
    }
    out = project_root / "drift_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
