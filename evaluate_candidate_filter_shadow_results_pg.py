# -*- coding: utf-8 -*-
"""
evaluate_candidate_filter_shadow_results_pg.py

v2_candidate_filter_shadow に保存された候補へ、確定結果・的中・払戻を反映します。

重要:
- LINE通知しません。
- 本番判定・購入処理を変更しません。
- 未評価行のみ更新します。
- 結果未取得・中止・不成立は評価保留または無効扱いにします。

通常は run_nightly_results_pg.py の結果取得後に実行します。

Start Command（単体テスト用）:
    python -u evaluate_candidate_filter_shadow_results_pg.py

Variables:
    DATABASE_URL
    TARGET_DATE=YYYY-MM-DD

任意:
    CANDIDATE_SHADOW_EVAL_ENABLED=1
    CANDIDATE_SHADOW_EVAL_REEVALUATE=0
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from db_pg import execute, fetch_all

JST = timezone(timedelta(hours=9))

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
ENABLED = os.getenv("CANDIDATE_SHADOW_EVAL_ENABLED", "1").strip().lower() in {
    "1", "true", "yes", "on"
}
REEVALUATE = os.getenv("CANDIDATE_SHADOW_EVAL_REEVALUATE", "0").strip().lower() in {
    "1", "true", "yes", "on"
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _norm_ticket(value: Any) -> str:
    import re
    import unicodedata

    text = unicodedata.normalize("NFKC", str(value or ""))
    nums = re.findall(r"[1-6]", text)
    if len(nums) >= 3:
        return f"{nums[0]}-{nums[1]}-{nums[2]}"
    return text.strip()


def _ensure_schema() -> None:
    ddl = [
        "alter table v2_candidate_filter_shadow add column if not exists evaluation_status text;",
        "alter table v2_candidate_filter_shadow add column if not exists evaluation_note text;",
        "create index if not exists ix_v2_candidate_filter_shadow_eval on v2_candidate_filter_shadow (race_date, evaluation_status);",
    ]
    for sql in ddl:
        execute(sql)


def _fetch_shadow_rows() -> List[Dict[str, Any]]:
    where = ["race_date=%s"]
    params: List[Any] = [TARGET_DATE]

    if not REEVALUATE:
        where.append("evaluated_at is null")

    return fetch_all(
        f"""
        select *
        from v2_candidate_filter_shadow
        where {' and '.join(where)}
        order by race_id, rule_id, ticket;
        """,
        tuple(params),
    )


def _fetch_results() -> Dict[str, Dict[str, Any]]:
    rows = fetch_all(
        """
        select
            race_id,
            trifecta_ticket,
            trifecta_payout_yen,
            result_status,
            race_status
        from v2_results
        where race_date=%s
        order by race_id;
        """,
        (TARGET_DATE,),
    )

    return {
        str(row.get("race_id")): row
        for row in rows
        if row.get("race_id")
    }


def main() -> None:
    print(
        "✅ evaluate_candidate_filter_shadow_results_pg.py "
        "VERSION 2026-08-01 result-eval-v1",
        flush=True,
    )
    print(
        f"TARGET_DATE={TARGET_DATE} ENABLED={ENABLED} REEVALUATE={REEVALUATE}",
        flush=True,
    )
    print(
        "Shadow結果評価のみ。LINE通知・本番判定・購入処理は変更しません。",
        flush=True,
    )

    if not ENABLED:
        print("CANDIDATE_SHADOW_EVAL_ENABLED=0 のためスキップします。", flush=True)
        return

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    _ensure_schema()

    shadow_rows = _fetch_shadow_rows()
    results_by = _fetch_results()

    evaluated = 0
    hits = 0
    no_result = 0
    invalid_result = 0
    updated = 0

    now_iso = datetime.now(JST).isoformat()

    by_rule: Dict[str, Dict[str, int]] = {}

    for row in shadow_rows:
        race_id = str(row.get("race_id") or "")
        rule_id = str(row.get("rule_id") or "UNKNOWN")
        ticket = _norm_ticket(row.get("ticket"))
        result = results_by.get(race_id)

        stats = by_rule.setdefault(
            rule_id,
            {
                "rows": 0,
                "evaluated": 0,
                "hits": 0,
                "investment": 0,
                "return": 0,
                "invalid": 0,
                "no_result": 0,
            },
        )
        stats["rows"] += 1

        if not result:
            no_result += 1
            stats["no_result"] += 1
            continue

        result_status = str(result.get("result_status") or "")
        race_status = str(result.get("race_status") or "")
        result_ticket = _norm_ticket(result.get("trifecta_ticket"))
        payout = _safe_int(result.get("trifecta_payout_yen"), 0)

        valid = (
            result_ticket
            and payout > 0
            and result_status == "official"
            and race_status == "official"
        )

        if not valid:
            invalid_result += 1
            stats["invalid"] += 1
            execute(
                """
                update v2_candidate_filter_shadow
                set
                    result_ticket=%s,
                    payout_yen=%s,
                    hit=false,
                    return_yen=0,
                    evaluated_at=%s,
                    evaluation_status=%s,
                    evaluation_note=%s,
                    updated_at=%s
                where id=%s;
                """,
                (
                    result_ticket or None,
                    payout,
                    now_iso,
                    "invalid_result",
                    f"result_status={result_status} race_status={race_status}",
                    now_iso,
                    row.get("id"),
                ),
            )
            updated += 1
            continue

        hit = ticket == result_ticket
        return_yen = payout if hit else 0

        execute(
            """
            update v2_candidate_filter_shadow
            set
                result_ticket=%s,
                payout_yen=%s,
                hit=%s,
                return_yen=%s,
                evaluated_at=%s,
                evaluation_status=%s,
                evaluation_note=%s,
                updated_at=%s
            where id=%s;
            """,
            (
                result_ticket,
                payout,
                hit,
                return_yen,
                now_iso,
                "evaluated",
                "",
                now_iso,
                row.get("id"),
            ),
        )

        evaluated += 1
        updated += 1
        stats["evaluated"] += 1
        stats["investment"] += _safe_int(row.get("investment_yen"), 100)

        if hit:
            hits += 1
            stats["hits"] += 1
            stats["return"] += payout

    print("\n=== candidate filter shadow daily evaluation ===", flush=True)
    print(f"shadow_rows={len(shadow_rows)}", flush=True)
    print(f"evaluated={evaluated}", flush=True)
    print(f"hits={hits}", flush=True)
    print(f"no_result={no_result}", flush=True)
    print(f"invalid_result={invalid_result}", flush=True)
    print(f"updated={updated}", flush=True)

    for rule_id in sorted(by_rule):
        stat = by_rule[rule_id]
        inv = stat["investment"]
        ret = stat["return"]
        hit_rate = (
            stat["hits"] / stat["evaluated"] * 100.0
            if stat["evaluated"] > 0
            else 0.0
        )
        roi = ret / inv * 100.0 if inv > 0 else 0.0
        profit = ret - inv

        print(
            f"{rule_id}: rows={stat['rows']} "
            f"evaluated={stat['evaluated']} "
            f"hits={stat['hits']} "
            f"hit_rate={hit_rate:.2f}% "
            f"investment={inv} return={ret} "
            f"profit={profit} ROI={roi:.2f}% "
            f"invalid={stat['invalid']} "
            f"no_result={stat['no_result']}",
            flush=True,
        )

    print("=== candidate filter shadow evaluation finished ===", flush=True)


if __name__ == "__main__":
    main()