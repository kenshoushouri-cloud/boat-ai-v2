def parse_odds3t(html: str, race_id: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")

    def make_row(ticket: str, odd: float) -> Dict[str, Any]:
        return {
            "race_id": race_id,
            "ticket": ticket,
            "odds": odd,
            "is_final": True,
            "fetched_at": _now_iso(),
        }

    valid_tickets = {
        f"{a}-{b}-{c}"
        for a, b, c in itertools.permutations([1, 2, 3, 4, 5, 6], 3)
    }

    rows: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------
    # A) tableタグ単位で1着艇ブロックを抽出（最も信頼性が高い）
    # ------------------------------------------------------------
    for table in soup.find_all("table"):
        tbl_text = table.get_text(" ", strip=True)
        # 3連単オッズ表以外はスキップ
        nums_in_table = re.findall(r"\d+(?:\.\d+)?", tbl_text)
        if len(nums_in_table) < 18:
            continue

        for tr in table.find_all("tr"):
            cells = [_clean_text(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
            for i in range(len(cells) - 2):
                # a-b-c odd のパターンを探す
                a, b, c = cells[i], cells[i+1], cells[i+2] if i+2 < len(cells) else ""
                if not (re.fullmatch(r"[1-6]", a) and re.fullmatch(r"[1-6]", b) and re.fullmatch(r"[1-6]", c)):
                    continue
                if len({a, b, c}) < 3:
                    continue
                # oddsは次のセルか同セル末尾の数値
                odd_str = cells[i+3] if i+3 < len(cells) else ""
                odd_val = _to_float(odd_str)
                if odd_val and odd_val > 0:
                    ticket = f"{a}-{b}-{c}"
                    if ticket in valid_tickets:
                        rows[ticket] = make_row(ticket, odd_val)

        if len(rows) >= 100:
            break

    if len(rows) >= 100:
        return sorted(rows.values(), key=lambda r: tuple(map(int, r["ticket"].split("-"))))

    # ------------------------------------------------------------
    # B) テキスト全体から「枠-枠-枠 オッズ」を正規表現で拾う
    # ------------------------------------------------------------
    rows = {}
    text = soup.get_text("\n", strip=True)

    # パターン1: 明示的なハイフン区切り「1-2-3 45.6」
    for m in re.finditer(
        r"([1-6])\s*[-－]\s*([1-6])\s*[-－]\s*([1-6])\s+([0-9]+(?:\.[0-9]+)?)",
        text
    ):
        a, b, c, o = m.group(1), m.group(2), m.group(3), m.group(4)
        if len({a, b, c}) < 3:
            continue
        ticket = f"{a}-{b}-{c}"
        if ticket in valid_tickets:
            rows[ticket] = make_row(ticket, float(o))

    # パターン2: スペース区切り「1 2 3 45.6」（テキスト化でハイフンが消えた場合）
    if len(rows) < 60:
        compact = re.sub(r"[ \t]+", " ", text)
        for m in re.finditer(
            r"(?<!\d)([1-6]) ([1-6]) ([1-6]) (\d+(?:\.\d+)?)(?!\d)",
            compact
        ):
            a, b, c, o = m.group(1), m.group(2), m.group(3), m.group(4)
            if len({a, b, c}) < 3:
                continue
            odd = float(o)
            if odd <= 0:
                continue
            ticket = f"{a}-{b}-{c}"
            if ticket in valid_tickets:
                rows.setdefault(ticket, make_row(ticket, odd))

    # パターン3: 行ごとに「枠番 オッズ」をrowspan的に復元
    # 公式の表構造: 1着固定→2着固定→3着4種+オッズ4種が1列に並ぶ
    if len(rows) < 60:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        current_first = None
        current_second = None
        for line in lines:
            tokens_line = re.findall(r"\d+(?:\.\d+)?", line)
            if len(tokens_line) == 1 and re.fullmatch(r"[1-6]", tokens_line[0]):
                # 1着or2着のヘッダ行
                val = int(tokens_line[0])
                if current_first is None:
                    current_first = val
                else:
                    current_second = val
            elif len(tokens_line) == 2:
                # 「3着 オッズ」行
                th_str, odd_str = tokens_line[0], tokens_line[1]
                if (current_first and current_second and
                        re.fullmatch(r"[1-6]", th_str)):
                    th = int(th_str)
                    odd = float(odd_str)
                    if len({current_first, current_second, th}) == 3 and odd > 0:
                        ticket = f"{current_first}-{current_second}-{th}"
                        if ticket in valid_tickets:
                            rows.setdefault(ticket, make_row(ticket, odd))
            elif len(tokens_line) == 0:
                # 区切り行でリセット
                current_second = None

    return sorted(rows.values(), key=lambda r: tuple(map(int, r["ticket"].split("-"))))