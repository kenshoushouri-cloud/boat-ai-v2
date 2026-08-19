def parse_deadline_time(html: str, race_no: int) -> Optional[str]:

    """

    指定race_noの締切予定時刻だけを取得する。

    重要:

    - 1R が 11R / 12R に部分一致しないようにする。

    - 全レースを内包する親divから最初の締切時刻を拾わない。

    - 対象Rを特定できない場合、別Rの時刻で補完しない。

    """

    soup = BeautifulSoup(html, "html.parser")

    target_no = int(race_no)

    # 全角→半角、空白正規化

    full_text = _clean_text(

        _zen_to_han(

            soup.get_text(" ", strip=True)

        )

    )

    # --------------------------------------------------------

    # 1. 「第nR」「nR」を正確に探す

    #

    # (?<!\d) / (?!\d) により、

    # 1R が 11R/12R に一致する事故を防ぐ。

    # --------------------------------------------------------

    target_pattern = re.compile(

        rf"(?<!\d)(?:第\s*)?{target_no}\s*R(?!\d)",

        flags=re.IGNORECASE,

    )

    deadline_patterns = [

        re.compile(r"締切予定時刻\s*(\d{1,2}:\d{2})"),

        re.compile(r"締切予定\s*(\d{1,2}:\d{2})"),

        re.compile(r"投票締切予定時刻\s*(\d{1,2}:\d{2})"),

        re.compile(r"発売締切\s*(\d{1,2}:\d{2})"),

        re.compile(r"締切時刻\s*(\d{1,2}:\d{2})"),

        re.compile(r"締切\s*(\d{1,2}:\d{2})"),

    ]

    # --------------------------------------------------------

    # 2. まずtable row / list itemのような

    #    小さい単位だけを見る。

    #

    #    div / section は親要素が全12Rを含むことがあるため

    #    ここでは使用しない。

    # --------------------------------------------------------

    for node in soup.find_all(["tr", "li"]):

        text = _clean_text(

            _zen_to_han(

                node.get_text(" ", strip=True)

            )

        )

        if not text:

            continue

        if not target_pattern.search(text):

            continue

        for pattern in deadline_patterns:

            match = pattern.search(text)

            if match:

                normalized = _normalize_hhmm(match.group(1))

                if normalized:

                    return normalized

        # 対象Rを含む小さい行なら時刻を探索

        times = re.findall(

            r"(?<!\d)(\d{1,2}:\d{2})(?!\d)",

            text,

        )

        # 締切時刻は通常ブロック後方にあるため後ろから確認

        for value in reversed(times):

            normalized = _normalize_hhmm(value)

            if normalized:

                return normalized

    # --------------------------------------------------------

    # 3. 本文上で対象Rから「次のR」までだけを切り出す。

    #

    # これにより1Rを探している時に2R以降の締切を

    # 誤って拾わない。

    # --------------------------------------------------------

    matches = list(target_pattern.finditer(full_text))

    for target_match in matches:

        start = target_match.start()

        # 対象Rの次に現れる「別のnR」を探す

        next_race_pattern = re.compile(

            r"(?<!\d)(?:第\s*)?([1-9]|1[0-2])\s*R(?!\d)",

            flags=re.IGNORECASE,

        )

        end = min(

            len(full_text),

            start + 500,

        )

        for next_match in next_race_pattern.finditer(

            full_text,

            target_match.end(),

        ):

            next_no = int(next_match.group(1))

            if next_no != target_no:

                end = min(end, next_match.start())

                break

        nearby = full_text[start:end]

        for pattern in deadline_patterns:

            match = pattern.search(nearby)

            if match:

                normalized = _normalize_hhmm(match.group(1))

                if normalized:

                    return normalized

        # 対象R区間内の時刻を最後の候補とする

        times = re.findall(

            r"(?<!\d)(\d{1,2}:\d{2})(?!\d)",

            nearby,

        )

        for value in reversed(times):

            normalized = _normalize_hhmm(value)

            if normalized:

                return normalized

    # --------------------------------------------------------

    # 4. rno指定の単一レースページの場合だけ、

    #    締切語そのものから取得。

    #

    # ただし、このページが複数Rを含んでいる場合には

    # 別Rの時刻を返す危険があるため、

    # 対象Rが本文に存在することを条件とする。

    # --------------------------------------------------------

    if target_pattern.search(full_text):

        for pattern in deadline_patterns:

            match = pattern.search(full_text)

            if match:

                normalized = _normalize_hhmm(match.group(1))

                if normalized:

                    return normalized

    # --------------------------------------------------------

    # 対象Rを特定できなければNULL。

    # 他レースの締切時刻を代入するより安全。

    # --------------------------------------------------------

    return None