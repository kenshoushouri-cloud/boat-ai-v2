"""ConoHa V5 retrospective one-day read-only TWO-population source adapter.

One local PostgreSQL day only; no writes, official HTTP, disk dump, model fit,
Forward or BUY. Produces preliminary, NEVER-VERIFIED source proposals for the
already tested v5.offline_research_two_population_day calculations.

Cohorts are deliberately separate: full-six exhib+K research-fit SHAPE and
K six-course history SHAPE. Results/F-L/refunds are POSTRACE and may only be
considered for retrospective training, never as features/selection at cutoff.

Real official 'no refund' evidence is UNAVAILABLE in v2_results.raw for
2026-10-20. We explicitly leave incident_free_verified=None and
refund_boats=None, so passing these to the projection yields no accepted fits.
Never synthesize positive attestations from 'official', normal K finish,
existing snapshot_at, or this module's structural counts.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import date
from typing import Any

from research.v5_recent_form_asof_audit_pg import (
    checked_date, local_connection_url,
)
from v5.offline_retrospective_counter_seed import (
    RetrospectiveKBoat, RetrospectiveResearchRace,
)
from v5.offline_research_two_population_day import (
    CourseHistoryRace, CourseKBoat, project_two_population_day,
)

# One bounded query; never selects postrace odds or a raw payload. A complete
# exhibition label is accepted for SHAPE only, not immutable as-of receipt.
SOURCES_SQL = """
WITH races AS MATERIALIZED (
  SELECT race_id,deadline_at
  FROM boat_data.races
  WHERE race_date=%s::date AND race_date>=DATE '2025-07-01'
), ex_labels AS MATERIALIZED (
  SELECT x.race_id,x.snapshot_label,max(x.snapshot_at) AS latest_capture,
         count(*) AS n,
         count(DISTINCT x.lane) FILTER (
            WHERE x.lane BETWEEN 1 AND 6
              AND x.exhibition_time_rank BETWEEN 1 AND 6) AS lanes6,
         count(DISTINCT x.exhibition_time_rank) FILTER (
            WHERE x.lane BETWEEN 1 AND 6
              AND x.exhibition_time_rank BETWEEN 1 AND 6) AS ranks6,
         count(*) FILTER (
            WHERE x.snapshot_at < r.deadline_at::timestamptz
              AND x.lane BETWEEN 1 AND 6
              AND x.exhibition_time_rank BETWEEN 1 AND 6) AS timestamp_rows
  FROM boat_data.exhibition_snapshots x
  JOIN races r USING(race_id)
  GROUP BY x.race_id,x.snapshot_label
), ex_pick AS MATERIALIZED (
  SELECT race_id,snapshot_label
  FROM (
    SELECT race_id,snapshot_label,
           row_number() OVER (
             PARTITION BY race_id
             ORDER BY latest_capture ASC,snapshot_label ASC NULLS LAST
           ) AS rn
    FROM ex_labels
    WHERE n=6 AND lanes6=6 AND ranks6=6 AND timestamp_rows=6
      AND snapshot_label IS NOT NULL
  ) eligible
  WHERE rn=1
)
SELECT r.race_id,
       e.lane,e.racer_number,e.racer_class,e.racer_class_text,
       k.racer_number AS k_racer_number,
       k.start_course,k.finish_position,k.finish_status,
       k.is_flying,k.is_late,
       x.exhibition_time_rank,
       p.snapshot_label,
       rs.result_status,rs.race_status,rs.trifecta_ticket
FROM races r
LEFT JOIN boat_data.entries e ON e.race_id=r.race_id
LEFT JOIN public.v2_result_entries k
  ON k.race_id=e.race_id AND k.lane=e.lane
 AND k.source='official_k_file'
LEFT JOIN ex_pick p ON p.race_id=r.race_id
LEFT JOIN boat_data.exhibition_snapshots x
  ON x.race_id=e.race_id AND x.lane=e.lane
 AND x.snapshot_label=p.snapshot_label
LEFT JOIN public.v2_results rs ON rs.race_id=r.race_id
ORDER BY r.race_id,e.lane
"""

@dataclass(frozen=True)
class SourceProposals:
    day: date
    race_total: int
    roster6: int
    k_course_shape6: int
    exhibition6: int
    fit_source_shape6: int
    fit_proposals: tuple[RetrospectiveResearchRace, ...]
    course_proposals: tuple[CourseHistoryRace, ...]
    # Absolutely no independent positive incident/refund/first-write evidence.
    first_capture_verified: bool = False
    retrospective_fit_authorized: bool = False
    forward_eligible: bool = False
    buy_eligible: bool = False


def _integer(v: object) -> int | None:
    return v if type(v) is int else None


# Same integer grade code as the official B-file parser. Never guess
# unrecognized values, or silently prefer one of two contradictory fields.
_CLASS_CODE = {1: "B2", 2: "B1", 3: "A2", 4: "A1"}
_CLASS_VALUES = frozenset(_CLASS_CODE.values())


def _normalized_class(code: object, label: object) -> str | None:
    grade_code = _integer(code)
    if grade_code is None and type(code) is str and code in ("1", "2", "3", "4"):
        grade_code = int(code)
    code_text = _CLASS_CODE.get(grade_code)
    direct_text = None
    if type(code) is str and code.strip().upper() in _CLASS_VALUES:
        direct_text = code.strip().upper()
    label_text = None
    if type(label) is str and label.strip():
        label_text = label.strip().upper()
        if label_text not in _CLASS_VALUES:
            return None
    known = [x for x in (code_text,direct_text,label_text) if x is not None]
    if not known or len(set(known)) != 1:
        return None
    # Nonempty unknown codes cannot be overridden by a valid label.
    if code is not None and code_text is None and direct_text is None:
        return None
    return known[0]


def _winner(ticket: object) -> int | None:
    if not isinstance(ticket,str):
        return None
    seg=ticket.split("-")
    if len(seg)!=3 or any(len(s)!=1 or s not in "123456" for s in seg):
        return None
    if len(set(seg))!=3:
        return None
    return int(seg[0])


def assemble_source_proposals(day: date, rows: list[dict[str, Any]]) -> SourceProposals:
    """Shape-only assembly. Caller must independently authenticate inputs.

    No invented official incident/refund positive flags are allowed, even for
    a complete six-lane normal-looking K race.
    """
    if type(day) is not date or not date(2025,7,1)<=day:
        raise ValueError("INVALID_DAY")
    groups: dict[str,list[dict[str,Any]]]={}
    for row in rows:
        rid=row.get("race_id")
        if (type(rid) is not str or rid[:8]!=day.strftime("%Y%m%d")
                or len(rid)!=14):
            raise ValueError("BAD_RACE_ID")
        groups.setdefault(rid,[]).append(row)
    fit: list[RetrospectiveResearchRace]=[]
    course: list[CourseHistoryRace]=[]
    roster_n=k_n=ex_n=joint_n=0
    for rid,group in sorted(groups.items()):
        lanes=[_integer(v.get("lane")) for v in group]
        roster = (
            len(group)==6 and set(lanes)==set(range(1,7))
            and len({v.get("racer_number") for v in group})==6
            and all(_integer(v.get("racer_number")) is not None
                    and _normalized_class(
                      v.get("racer_class"),v.get("racer_class_text")
                    ) is not None
                    for v in group)
        )
        roster_n+=int(roster)
        k_shape= (
            roster
            and all(_integer(v.get("k_racer_number"))==v["racer_number"]
                    and _integer(v.get("start_course")) in range(1,7)
                    and _integer(v.get("finish_position")) in range(1,7)
                    and v.get("is_flying") is False
                    and v.get("is_late") is False
                    for v in group)
            and {v["start_course"] for v in group}==set(range(1,7))
            and {v["finish_position"] for v in group}==set(range(1,7))
            and all(v.get("result_status")=="official"
                    and v.get("race_status")=="official" for v in group)
        )
        k_n+=int(k_shape)
        exhib=(
            roster and len({v.get("snapshot_label") for v in group})==1
            and all(type(v.get("snapshot_label")) is str
                    for v in group)
            and {v.get("exhibition_time_rank") for v in group}==set(range(1,7))
        )
        ex_n+=int(exhib)
        join=k_shape and exhib and _winner(group[0].get("trifecta_ticket")) is not None
        if join:
            winner=_winner(group[0].get("trifecta_ticket"))
            join=(
                next(v for v in group if v["lane"]==winner)["finish_position"]==1
            )
        joint_n+=int(join)
        if not k_shape:
            continue
        course_boats=tuple(
            CourseKBoat(
                lane=v["lane"],racer_number=v["racer_number"],
                start_course=v["start_course"],finish_position=v["finish_position"],
                is_flying=v["is_flying"],is_late=v["is_late"],
            ) for v in sorted(group,key=lambda x:x["lane"])
        )
        course.append(CourseHistoryRace(
            rid,course_boats,"UNVERIFIED",None,None
        ))
        if not join:
            continue
        fit_boats=tuple(
            RetrospectiveKBoat(
                lane=v["lane"],racer_number=v["racer_number"],
                racer_class=_normalized_class(
                    v.get("racer_class"),v.get("racer_class_text")
                ),
                exhibition_rank=v["exhibition_time_rank"],
                start_course=v["start_course"],finish_position=v["finish_position"],
                is_flying=v["is_flying"],is_late=v["is_late"],
            ) for v in sorted(group,key=lambda x:x["lane"])
        )
        fit.append(RetrospectiveResearchRace(
            rid,winner,fit_boats,"UNVERIFIED",None,None
        ))
    return SourceProposals(
        day,len(groups),roster_n,k_n,ex_n,joint_n,
        tuple(fit),tuple(course)
    )


def held_summary(src: SourceProposals) -> str:
    # The projection refuses all unverified proposals; this is intentional.
    held=project_two_population_day(
        src.day,src.fit_proposals,src.course_proposals
    )
    if held.state.completed_races or held.fit_race_ids or held.course_race_ids:
        raise RuntimeError("UNEXPECTED_RESEARCH_STATE_PROMOTION")
    return "\n".join((
        f"V5_READONLY_DAY={src.day.isoformat()}",
        f"RACES={src.race_total}",
        f"ROSTER_6={src.roster6}",
        f"K_COURSE_SHAPE_6={src.k_course_shape6}",
        f"EXHIBITION_TIMESTAMP_SHAPE_6_NOT_PROOF={src.exhibition6}",
        f"JOINT_SOURCE_SHAPE_6_NOT_PROVEN={src.fit_source_shape6}",
        f"FIT_PROPOSALS_UNVERIFIED={len(src.fit_proposals)}",
        f"COURSE_PROPOSALS_UNVERIFIED={len(src.course_proposals)}",
        "RESEARCH_FIT_ACCEPTED=0",
        "K_COURSE_FIT_ACCEPTED=0",
        "UNVERIFIED_REFUND_AND_INCIDENT_GATES=HOLD",
        "FROZEN_PRIOR_DAY_COUNTERS=NOT_BUILT",
        "FIRST_CAPTURE_VERIFIED=0",
        "FORWARD_ELIGIBLE=0",
        "BUY_ELIGIBLE=0",
        "V5_ONE_DAY_REAL_SOURCE_PREVIEW_READONLY_HOLD",
    ))


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date",required=True)
    parser.add_argument("--counter-shape-preview",action="store_true",
                        help="Only research Counter FAMILY TOTALS; no fitted state")
    args=parser.parse_args(argv)
    day=checked_date(args.date)
    url=local_connection_url(os.getenv("DATABASE_URL",""))
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(url,row_factory=dict_row,autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout='20s'")
            cur.execute("SET LOCAL lock_timeout='1000ms'")
            cur.execute("SET LOCAL work_mem='8MB'")
            cur.execute(SOURCES_SQL,(day,))
            rows=cur.fetchall()
        conn.rollback()
    src=assemble_source_proposals(day,list(rows))
    print(held_summary(src))
    if args.counter_shape_preview:
        # Import here to keep the source-only path light and avoid cyclic imports.
        from v5.offline_unverified_counter_shape_preview import (
            rehearse_unverified_counter_shapes, preview_summary,
        )
        print(preview_summary(rehearse_unverified_counter_shapes(src)))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
