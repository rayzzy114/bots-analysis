from __future__ import annotations

import argparse
from pathlib import Path

PATTERNS = (
    'рџ',
    'РќР',
    'С‹Р',
    'вЂ',
    'пё',
    'вќ',
    'Џ',
    'Ќ',
    '\ufffd',
)


def check_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding='utf-8')
    except Exception as exc:
        return [f'{path}: unreadable utf-8 ({exc})']
    hits: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for p in PATTERNS:
            if p in line:
                hits.append(f'{path}:{lineno}: {line.strip()}')
                break
    return hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('paths', nargs='*', default=['app', 'main.py', 'dev.py', 'README.md'])
    args = parser.parse_args()

    files: list[Path] = []
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            files.extend([f for f in p.rglob('*') if f.is_file()])
        elif p.is_file():
            files.append(p)

    bad: list[str] = []
    for f in files:
        if f.suffix in {'.py', '.md', '.txt', '.json', '.yaml', '.yml', '.env'} or f.name in {'.env', '.env.example'}:
            bad.extend(check_file(f))

    if bad:
        print('Mojibake/bakemoji candidates found:')
        for row in bad:
            print(row)
        return 1

    print('No mojibake/bakemoji patterns found.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
