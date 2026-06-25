"""Fetch the latest CSI 300 constituent list from Sina Finance.

Saves a plain-text file with one symbol per line (e.g., 000001.SZ) to the
configured data directory. This avoids relying on the iFind MCP stock-list
tool, which can be unstable for index-constituent queries.
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root.parent))

from aifa_quant.config.settings import Settings


def code_to_symbol(code: str) -> str:
    """Map 6-digit Chinese stock code to symbol with exchange suffix."""
    code = code.strip()
    # Shenzhen: 000/001/002/003/300/301; Shanghai: 600/601/603/605/688/689
    if code.startswith(("0", "2", "3")):
        return f"{code}.SZ"
    return f"{code}.SH"


def fetch_csi300_symbols() -> list[str]:
    """Fetch CSI 300 components from Sina Finance paginated table."""
    base_url = "https://vip.stock.finance.sina.com.cn/corp/view/vII_NewestComponent.php"
    codes: list[str] = []
    for page in range(1, 20):
        resp = requests.get(base_url, params={"page": page, "indexid": "000300"}, timeout=30)
        resp.encoding = "gb2312"
        soup = BeautifulSoup(resp.text, "html.parser")
        page_codes = []
        for tr in soup.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells and re.match(r"^\d{6}$", cells[0]):
                page_codes.append(cells[0])
        if not page_codes:
            break
        codes.extend(page_codes)
        if len(codes) >= 300:
            break
    return [code_to_symbol(c) for c in codes]


def main() -> None:
    settings = Settings()
    out_dir = settings.data_dir_path
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "csi300_symbols.txt"

    symbols = fetch_csi300_symbols()
    if len(symbols) != 300:
        print(f"[yellow]警告：只获取到 {len(symbols)} 只成分股，预期 300 只[/yellow]")

    out_path.write_text("\n".join(symbols), encoding="utf-8")
    print(f"[green]已保存 {len(symbols)} 只沪深300成分股到 {out_path}[/green]")


if __name__ == "__main__":
    main()
