#!/usr/bin/env python3
"""Pre-commit hook: block commits that stage sensitive files.

Stops .env, *.duckdb, model artifacts, and obvious secret-key patterns
from entering git history. Install with:

    cp scripts/check_no_secrets.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit  # on Unix
"""

from __future__ import annotations

import sys
from pathlib import Path

BLOCKED_PATTERNS = [".env", ".env.local", ".env.production"]
BLOCKED_SUFFIXES = [".duckdb", ".pkl", ".joblib", ".lgb", ".xgb"]
SECRET_PATTERNS = ["SUPABASE_SERVICE_ROLE_KEY", "TUSHARE_TOKEN", "IFIND_STOCK_MCP_TOKEN"]


def main() -> int:
    # Read staged files via `git diff --cached --name-only`.
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=False,
    )
    files = [f for f in result.stdout.splitlines() if f.strip()]
    if not files:
        return 0

    blocked: list[str] = []
    for f in files:
        name = Path(f).name
        if name in BLOCKED_PATTERNS or any(name.endswith(suf) for suf in BLOCKED_SUFFIXES):
            blocked.append(f)

    # Scan staged content for secret tokens.
    secret_hits: list[str] = []
    for f in files:
        try:
            text = Path(f).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat in SECRET_PATTERNS:
            if pat in text and "SUPABASE_SERVICE_ROLE_KEY=" not in text.split(pat)[0].split("\n")[-1]:
                # Allow example files like .env.example.
                if name.endswith(".example") or name == ".env.example":
                    continue
                secret_hits.append(f"{f}: contains {pat}")

    if blocked:
        print("❌ 检测到敏感文件被暂存，已阻止提交：", file=sys.stderr)
        for f in blocked:
            print(f"   {f}", file=sys.stderr)
        print("   这些文件已在 .gitignore 中。如确需提交，请改用 .example 后缀。", file=sys.stderr)
    if secret_hits:
        print("❌ 检测到疑似密钥字符串，已阻止提交：", file=sys.stderr)
        for h in secret_hits:
            print(f"   {h}", file=sys.stderr)

    return 1 if (blocked or secret_hits) else 0


if __name__ == "__main__":
    raise SystemExit(main())
