from pathlib import Path

ENV_PATH = Path(__file__).parent.parent.parent / ".env"


def update_env_var(key: str, value: str):
    """Update or add a key=value pair in .env file."""
    env_path = ENV_PATH
    lines = []
    found = False

    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith(f"{key}="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line)

    if not found:
        lines.append(f"{key}={value}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def read_env_var(key: str, default: str = "") -> str:
    """Read a single key from .env."""
    env_path = ENV_PATH
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith(f"{key}="):
                    return line.strip().split("=", 1)[1].strip()
    return default
