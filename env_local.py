"""加载 .env.local / .env 到 os.environ（不覆盖已有环境变量）。"""

from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def load_local_env() -> None:
    for name in (".env.local", ".env"):
        path = _ROOT / name
        if not path.is_file():
            continue
        override = name == ".env.local"
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if not key:
                continue
            if override or key not in os.environ:
                os.environ[key] = val


load_local_env()
