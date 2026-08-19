# -*- coding: utf-8 -*-
from pathlib import Path
import re

p = Path(__file__).resolve().parent / "repair_month_all_pg.py"
if not p.exists():
    raise FileNotFoundError(f"repair_month_all_pg.py not found: {p}")

s = p.read_text(encoding="utf-8")
backup = p.with_name("repair_month_all_pg_v9_backup.py")
backup.write_text(s, encoding="utf-8")

new = r"""def parse_deadline_table(html: str) -> Dict[int, str]:
    # racelist上部の「1R～12R」と「締切予定時刻」を同じ列位置で対応付ける。
    soup = BeautifulSoup(html, "html.parser")

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for i, tr in enumerate(rows):
            texts = [
                _clean_text(_zen_to_han(c.get_text(" ", strip=True)))
                for c in tr.find_all(["th", "td"])
            ]

            race_cols: Dict[int, int] = {}
            for col, text in enumerate(texts):
                m = re.fullmatch(
                    r"(?:第\\s*)?([1-9]|1[0-2])\\s*R",
                    text,
                    flags=re.IGNORECASE,
                )
                if m:
                    race_cols[col] = int(m.group(1))

            if len(race_cols) < 3:
                continue

            for tr2 in rows[i + 1:i + 5]:
                texts2 = [
                    _clean_text(_zen_to_han(c.get_text(" ", strip=True)))
                    for c in tr2.find_all(["th", "td"])
                ]
                if "締切" not in " ".join(texts2):
                    continue

                result: Dict[int, str] = {}
                for col, mapped_race_no in race_cols.items():
                    if col >= len(texts2):
                        continue
                    m = re.search(
                        r"(?<!\\d)(\\d{1,2}:\\d{2})(?!\\d)",
                        texts2[col],
                    )
                    if not m:
                        continue
                    value = _normalize_hhmm(m.group(1))
                    if value:
                        result[mapped_race_no] = value

                if len(result) >= 3:
                    return result

    return {}


def parse_deadline_time(html: str, race_no: int) -> Optional[str]:
    # v10: 文字列近傍検索を廃止。解析失敗時は誤時刻ではなくNone。
    return parse_deadline_table(html).get(int(race_no))


"""

pattern = re.compile(
    r"def parse_deadline_time\\(html: str, race_no: int\\) -> Optional\\[str\\]:.*?(?=def make_deadline_at\\()",
    re.S,
)
if not pattern.search(s):
    raise RuntimeError("parse_deadline_time block not found")
s = pattern.sub(new, s, count=1)

# バージョン文字列だけ安全に更新
s = re.sub(
    r"2026-08-19 deadline-race-scope-v9",
    "2026-08-19 deadline-table-v10",
    s,
)

compile(s, str(p), "exec")
p.write_text(s, encoding="utf-8")
print("PATCHED:", p)
print("BACKUP:", backup)
print("SYNTAX=PASS")