# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(__file__).resolve().parent / "repair_month_all_pg.py"
if not p.exists():
    raise FileNotFoundError(f"repair_month_all_pg.py not found: {p}")

s = p.read_text(encoding="utf-8")
backup = p.with_name("repair_month_all_pg_v9_backup.py")
backup.write_text(s, encoding="utf-8")

start_marker = "def parse_deadline_time(html: str, race_no: int) -> Optional[str]:"
end_marker = "def make_deadline_at("

start = s.find(start_marker)
if start < 0:
    raise RuntimeError("parse_deadline_time start not found")

end = s.find(end_marker, start)
if end < 0:
    raise RuntimeError("make_deadline_at start not found")

new_block = """def parse_deadline_table(html: str) -> Dict[int, str]:
    \"\"\"
    公式racelistの1R～12Rと締切予定時刻を列位置で対応付ける。
    \"\"\"
    soup = BeautifulSoup(html, "html.parser")

    for table in soup.find_all("table"):
        rows = table.find_all("tr")

        for i, tr in enumerate(rows):
            cells = tr.find_all(["th", "td"])
            texts = [
                _clean_text(_zen_to_han(c.get_text(" ", strip=True)))
                for c in cells
            ]

            race_cols: Dict[int, int] = {}
            for col, text in enumerate(texts):
                match = re.fullmatch(
                    r"(?:第\\s*)?([1-9]|1[0-2])\\s*R",
                    text,
                    flags=re.IGNORECASE,
                )
                if match:
                    race_cols[col] = int(match.group(1))

            if len(race_cols) < 3:
                continue

            for tr2 in rows[i + 1:i + 6]:
                cells2 = tr2.find_all(["th", "td"])
                texts2 = [
                    _clean_text(_zen_to_han(c.get_text(" ", strip=True)))
                    for c in cells2
                ]

                if "締切" not in " ".join(texts2):
                    continue

                result: Dict[int, str] = {}
                for col, mapped_race_no in race_cols.items():
                    if col >= len(texts2):
                        continue

                    match = re.search(
                        r"(?<!\\d)(\\d{1,2}:\\d{2})(?!\\d)",
                        texts2[col],
                    )
                    if not match:
                        continue

                    value = _normalize_hhmm(match.group(1))
                    if value:
                        result[mapped_race_no] = value

                if len(result) >= 3:
                    return result

    return {}


def parse_deadline_time(html: str, race_no: int) -> Optional[str]:
    \"\"\"
    v10: 公式racelistの時刻表から対象race_noの締切時刻だけを取得する。
    誤取得防止のため、解析できない場合は別レースの時刻へフォールバックしない。
    \"\"\"
    return parse_deadline_table(html).get(int(race_no))


"""

s = s[:start] + new_block + s[end:]
s = s.replace(
    "2026-08-19 deadline-race-scope-v9",
    "2026-08-19 deadline-table-v10",
)

# 書き込み前に構文確認
compile(s, str(p), "exec")
p.write_text(s, encoding="utf-8")

print("PATCHED:", p)
print("BACKUP:", backup)
print("SYNTAX=PASS")