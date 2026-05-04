# -*- coding: utf-8 -*-
"""
stable / ana の個別バックテスト結果を統合し、
実運用と同じ 1日1,000円 制限で再シミュレーションする。

目的:
- stable単体、ana単体の検証結果は残す
- 最終成績は portfolio として評価する
- 結果を見てから選ばないように、hit/profitではなくEV・race_score等で選別する

使い方:
    from backtest.portfolio_runner import run_portfolio_backtest

    run_portfolio_backtest(
        start_date="2026-04-01",
        end_date="2026-04-03",
        stable_run_id="test_stable_20260401_20260403",
        ana_run_id="test_ana_20260401_20260403",
        portfolio_run_id="test_portfolio_20260401_20260403",
    )
"""

import json
import urllib.parse
from datetime import datetime, timedelta

import requests as http_requests

from db.client import upsert
from config.settings import SUPABASE_URL, SUPABASE_KEY, MODEL_VERSION


HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


UNIT_YEN = 100
DAILY_BUDGET_YEN = 1000
DAILY_MAX_POINTS = DAILY_BUDGET_YEN // UNIT_YEN

# モードごとの目安上限
MODE_DAILY_LIMITS = {
    "stable": 6,
    "ana": 4,
}


# ============================================================
# utility
# ============================================================

def _daterange(start_str, end_str):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")

    cur = start
    while cur <= end:
        yield cur.strftime("%Y-%m-%d")
        cur += timedelta(days=1)


def _safe_float(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def _safe_int(v, default=0):
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default


def _strip_db_generated_fields(row):
    """
    Supabaseから取得した既存行を別run_idで再保存するため、
    idなどDB生成系の値を除去する。
    """
    row = dict(row)

    for key in [
        "id",
        "created_at",
        "updated_at",
        "inserted_at",
    ]:
        row.pop(key, None)

    return row


# ============================================================
# Supabase fetch
# ============================================================

def _fetch_backtest_rows(run_id, race_date):
    encoded_run_id = urllib.parse.quote(run_id)

    url = (
        f"{SUPABASE_URL}/rest/v1/v2_backtest_races"
        f"?select=*"
        f"&run_id=eq.{encoded_run_id}"
        f"&race_date=eq.{race_date}"
        f"&buy_flag=eq.true"
        f"&limit=1000"
    )

    try:
        res = http_requests.get(url, headers=HEADERS, timeout=20)
        if not res.ok:
            print(f"fetch error: {run_id} {race_date} {res.status_code} {res.text[:200]}")
            return []

        return res.json()

    except Exception as e:
        print(f"fetch exception: {run_id} {race_date} {e}")
        return []


# ============================================================
# portfolio selection
# ============================================================

def _priority_score(row):
    """
    注意:
    hit_flag / payout_yen / profit_yen / winning_ticket は絶対に使わない。
    実際の購入前に分かる情報だけで優先順位を決める。
    """
    mode = row.get("mode") or ""

    ev = _safe_float(row.get("max_ev"), 0.0)
    race_score = _safe_float(row.get("race_score"), 0.0)
    prob = _safe_float(row.get("top1_prob"), 0.0)
    odds = _safe_float(row.get("top1_odds"), 0.0)

    mode_bonus = 0.08 if mode == "stable" else 0.0

    scenario_bonus = {
        "attack": 0.06,
        "escape": 0.04,
        "hole": 0.02,
        "mixed": 0.00,
        "unknown": -1.00,
    }.get(row.get("scenario_type"), 0.0)

    # 超高オッズの暴れすぎを少し抑える
    odds_penalty = 0.0
    if odds >= 80:
        odds_penalty = 0.20
    elif odds >= 50:
        odds_penalty = 0.08

    return ev + race_score + prob + mode_bonus + scenario_bonus - odds_penalty


def _parse_bets(row):
    """
    bets_json があれば複数買い目を見る。
    なければ top1_ticket だけで処理する。
    """
    bets_json = row.get("bets_json")

    if bets_json:
        try:
            bets = json.loads(bets_json)
            if isinstance(bets, list) and bets:
                return bets
        except Exception:
            pass

    ticket = row.get("top1_ticket")
    if not ticket:
        return []

    return [{
        "ticket": ticket,
        "prob": row.get("top1_prob"),
        "odds": row.get("top1_odds"),
        "ev": row.get("max_ev"),
        "bet_type": "trifecta",
    }]


def _apply_portfolio_budget(rows):
    """
    stable + ana の候補から、1日1,000円以内に絞る。
    """
    rows = list(rows)
    rows.sort(key=_priority_score, reverse=True)

    selected = []
    rejected = []

    used_total_points = 0
    used_by_mode = {
        "stable": 0,
        "ana": 0,
    }

    seen_ticket_keys = set()

    for row in rows:
        mode = row.get("mode") or "unknown"
        bets = _parse_bets(row)

        if not bets:
            row["portfolio_buy_flag"] = False
            row["portfolio_skip_reason"] = "買い目なし"
            rejected.append(row)
            continue

        points = len(bets)

        ticket_key = (
            row.get("race_id"),
            ",".join(sorted([b.get("ticket", "") for b in bets])),
        )

        if ticket_key in seen_ticket_keys:
            row["portfolio_buy_flag"] = False
            row["portfolio_skip_reason"] = "重複買い目"
            rejected.append(row)
            continue

        if used_total_points + points > DAILY_MAX_POINTS:
            row["portfolio_buy_flag"] = False
            row["portfolio_skip_reason"] = "1日1,000円上限"
            rejected.append(row)
            continue

        mode_limit = MODE_DAILY_LIMITS.get(mode)
        if mode_limit is not None:
            if used_by_mode.get(mode, 0) + points > mode_limit:
                row["portfolio_buy_flag"] = False
                row["portfolio_skip_reason"] = f"{mode}モード上限"
                rejected.append(row)
                continue

        row["portfolio_buy_flag"] = True
        row["portfolio_skip_reason"] = None
        row["portfolio_points"] = points
        row["portfolio_stake_yen"] = points * UNIT_YEN

        selected.append(row)
        seen_ticket_keys.add(ticket_key)
        used_total_points += points

        if mode in used_by_mode:
            used_by_mode[mode] += points

    return selected, rejected


def _recalculate_row_result(row):
    """
    既存バックテスト結果を portfolio 用に再計算する。
    元の stake_yen は使わず、portfolio の点数で計算する。
    """
    stake = _safe_int(row.get("portfolio_stake_yen"), 0)
    payout = _safe_int(row.get("payout_yen"), 0)
    hit = bool(row.get("hit_flag"))

    profit = payout - stake

    row["stake_yen"] = stake
    row["profit_yen"] = profit
    row["trigami"] = bool(hit and payout < stake)

    return row


def _make_rejected_row(row):
    """
    portfolioで不採用になった候補を保存用に整える。
    """
    row["buy_flag"] = False
    row["skip_reason"] = row.get("portfolio_skip_reason")
    row["stake_yen"] = 0
    row["payout_yen"] = 0
    row["profit_yen"] = 0
    row["hit_flag"] = False
    row["trigami"] = False
    return row


# ============================================================
# summary
# ============================================================

def _calc_max_losing_streak(adopted):
    max_streak = 0
    cur = 0

    for r in adopted:
        if r.get("hit_flag"):
            cur = 0
        else:
            cur += 1
            max_streak = max(max_streak, cur)

    return max_streak


def _calc_max_drawdown(adopted):
    equity = 0
    peak = 0
    max_dd = 0

    for r in adopted:
        equity += _safe_int(r.get("profit_yen"), 0)
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)

    return max_dd


def _summarize(rows, run_id, start_date, end_date):
    adopted = [r for r in rows if r.get("portfolio_buy_flag")]
    hits = [r for r in adopted if r.get("hit_flag")]
    trigamis = [r for r in hits if r.get("trigami")]

    total_points = sum(_safe_int(r.get("portfolio_points"), 0) for r in adopted)
    total_stake = sum(_safe_int(r.get("stake_yen"), 0) for r in adopted)
    total_payout = sum(_safe_int(r.get("payout_yen"), 0) for r in adopted)
    profit = total_payout - total_stake

    roi = total_payout / total_stake * 100 if total_stake > 0 else 0.0
    hit_rate = len(hits) / len(adopted) * 100 if adopted else 0.0
    trigami_rate = len(trigamis) / len(hits) * 100 if hits else 0.0

    adopted_days = sorted(set(r.get("race_date") for r in adopted))
    days = len(adopted_days) if adopted_days else 1

    avg_points_per_day = total_points / days if days else 0.0
    avg_stake_per_day = total_stake / days if days else 0.0
    avg_profit_per_day = profit / days if days else 0.0

    max_losing_streak = _calc_max_losing_streak(adopted)
    max_drawdown = _calc_max_drawdown(adopted)

    no_hit_days = 0
    for d in adopted_days:
        day_rows = [r for r in adopted if r.get("race_date") == d]
        if day_rows and not any(r.get("hit_flag") for r in day_rows):
            no_hit_days += 1

    print("\n" + "=" * 60)
    print(f"統合バックテスト結果: {start_date} -> {end_date}")
    print("=" * 60)
    print(f"採用レース数:       {len(adopted)}")
    print(f"採用点数:           {total_points}点")
    print(f"的中レース数:       {len(hits)}")
    print(f"的中率:             {hit_rate:.1f}%")
    print(f"投資額:             {total_stake:,}円")
    print(f"回収額:             {total_payout:,}円")
    print(f"損益:               {profit:+,}円")
    print(f"回収率:             {roi:.1f}%")
    print(f"トリガミ率:         {trigami_rate:.1f}%")
    print(f"最大連敗:           {max_losing_streak}")
    print(f"最大DD:             {max_drawdown:,}円")
    print(f"的中なし日数:       {no_hit_days}日")
    print(f"1日平均点数:        {avg_points_per_day:.1f}点")
    print(f"1日平均投資:        {avg_stake_per_day:.0f}円")
    print(f"1日平均損益:        {avg_profit_per_day:+.0f}円")

    print("\n--- モード別 ---")
    mode_stats = {}

    for r in adopted:
        m = r.get("mode", "unknown")
        if m not in mode_stats:
            mode_stats[m] = {
                "count": 0,
                "points": 0,
                "hit": 0,
                "stake": 0,
                "payout": 0,
            }

        mode_stats[m]["count"] += 1
        mode_stats[m]["points"] += _safe_int(r.get("portfolio_points"), 0)
        mode_stats[m]["stake"] += _safe_int(r.get("stake_yen"), 0)
        mode_stats[m]["payout"] += _safe_int(r.get("payout_yen"), 0)

        if r.get("hit_flag"):
            mode_stats[m]["hit"] += 1

    for m, s in sorted(mode_stats.items()):
        roi_m = s["payout"] / s["stake"] * 100 if s["stake"] > 0 else 0.0
        hit_m = s["hit"] / s["count"] * 100 if s["count"] > 0 else 0.0
        profit_m = s["payout"] - s["stake"]

        print(
            f"  {m}: {s['count']}レース/{s['points']}点 "
            f"的中{hit_m:.1f}% ROI{roi_m:.1f}% "
            f"損益{profit_m:+,}円"
        )

    summary = {
        "run_id": run_id,
        "model_version": MODEL_VERSION,
        "target_start_date": start_date,
        "target_end_date": end_date,
        "total_races": len(rows),
        "adopted_races": len(adopted),
        "hit_races": len(hits),
        "hit_rate": round(hit_rate, 2),
        "total_stake_yen": total_stake,
        "total_payout_yen": total_payout,
        "profit_yen": profit,
        "roi": round(roi, 2),
        "trigami_rate": round(trigami_rate, 2),
        "scenario_stats": "",
        "note": (
            f"portfolio stable+ana "
            f"points={total_points} "
            f"avg_points={avg_points_per_day:.1f}/day "
            f"max_losing_streak={max_losing_streak} "
            f"max_drawdown={max_drawdown}"
        ),
    }

    upsert("v2_backtest_runs", summary, on_conflict="run_id")
    return summary


# ============================================================
# main
# ============================================================

def run_portfolio_backtest(
    start_date,
    end_date,
    stable_run_id,
    ana_run_id,
    portfolio_run_id=None,
):
    """
    stable / ana の既存バックテスト結果を統合する。
    """

    if portfolio_run_id is None:
        portfolio_run_id = f"{MODEL_VERSION}_portfolio_{start_date}_{end_date}"

    dates = list(_daterange(start_date, end_date))
    total_days = len(dates)

    print("=== portfolio統合バックテスト開始 ===", flush=True)
    print(f"期間: {start_date} -> {end_date} / {total_days}日", flush=True)
    print(f"stable_run_id: {stable_run_id}", flush=True)
    print(f"ana_run_id: {ana_run_id}", flush=True)
    print(f"portfolio_run_id: {portfolio_run_id}", flush=True)
    print(f"1日上限: {DAILY_BUDGET_YEN}円 / {DAILY_MAX_POINTS}点", flush=True)

    all_selected = []
    all_rows = []

    for day_index, race_date in enumerate(dates, 1):
        print(f"[portfolio] {race_date} 開始 ({day_index}/{total_days})", flush=True)

        stable_rows = _fetch_backtest_rows(stable_run_id, race_date)
        ana_rows = _fetch_backtest_rows(ana_run_id, race_date)

        rows = []

        for r in stable_rows:
            r = _strip_db_generated_fields(r)
            r["mode"] = r.get("mode") or "stable"
            rows.append(r)

        for r in ana_rows:
            r = _strip_db_generated_fields(r)
            r["mode"] = r.get("mode") or "ana"
            rows.append(r)

        if not rows:
            print(f"[portfolio] {race_date} 候補なし ({day_index}/{total_days})", flush=True)
            continue

        selected, rejected = _apply_portfolio_budget(rows)

        day_points = 0
        day_profit = 0
        day_hits = 0

        for row in selected:
            row = _recalculate_row_result(row)
            row = _strip_db_generated_fields(row)

            row["run_id"] = portfolio_run_id
            row["model_version"] = MODEL_VERSION
            row["buy_flag"] = True
            row["skip_reason"] = None

            day_points += _safe_int(row.get("portfolio_points"), 0)
            day_profit += _safe_int(row.get("profit_yen"), 0)
            if row.get("hit_flag"):
                day_hits += 1

            upsert(
                "v2_backtest_races",
                row,
                on_conflict="race_id,run_id,mode",
            )

            all_selected.append(row)
            all_rows.append(row)

        for row in rejected:
            row = _make_rejected_row(row)
            row = _strip_db_generated_fields(row)

            row["run_id"] = portfolio_run_id
            row["model_version"] = MODEL_VERSION

            upsert(
                "v2_backtest_races",
                row,
                on_conflict="race_id,run_id,mode",
            )

            all_rows.append(row)

        print(
            f"[portfolio] {race_date} 完了 ({day_index}/{total_days}) "
            f"候補={len(rows)} 採用={len(selected)}R/{day_points}点 "
            f"的中={day_hits} 日次損益={day_profit:+,}円 "
            f"除外={len(rejected)}",
            flush=True,
        )

    if not all_rows:
        print("統合対象なし", flush=True)
        return None

    return _summarize(
        rows=all_selected,
        run_id=portfolio_run_id,
        start_date=start_date,
        end_date=end_date,
    )


if __name__ == "__main__":
    run_portfolio_backtest(
        start_date="2026-04-01",
        end_date="2026-04-03",
        stable_run_id="test_stable_20260401_20260403",
        ana_run_id="test_ana_20260401_20260403",
        portfolio_run_id="test_portfolio_20260401_20260403",
    )