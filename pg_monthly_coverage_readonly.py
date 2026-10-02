import os
import psycopg
from psycopg.rows import dict_row

url = os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit("DATABASE_URL is required")

with psycopg.connect(url, row_factory=dict_row, autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("set transaction read only")
        cur.execute("""
            with m as (
              select to_char(r.race_date, 'YYYY-MM') as month_key,
                     count(distinct r.race_id)::int races,
                     count(distinct e.race_id) filter (where e.n=6)::int entries6,
                     count(distinct rs.race_id)::int results,
                     count(distinct re.race_id) filter (where re.n=6)::int result_entries6,
                     count(distinct o.race_id) filter (where o.n=120)::int odds120
              from v2_races r
              left join (select race_id,count(distinct lane) n from v2_race_entries group by race_id) e on e.race_id=r.race_id
              left join v2_results rs on rs.race_id=r.race_id
              left join (select race_id,count(distinct lane) n from v2_result_entries group by race_id) re on re.race_id=r.race_id
              left join (select race_id,count(distinct ticket) filter (where odds is not null and odds>0) n from v2_odds_trifecta group by race_id) o on o.race_id=r.race_id
              where r.race_date >= date '2025-07-01'
              group by 1
            )
            select * from m order by month_key
        """)
        print("MONTH|RACES|ENTRIES6|RESULTS|RESULT_ENTRIES6|ODDS120")
        for x in cur.fetchall():
            print(f"{x['month_key']}|{x['races']}|{x['entries6']}|{x['results']}|{x['result_entries6']}|{x['odds120']}")
print("CANDIDATE_V4_MONTHLY_COVERAGE=PASS_READ_ONLY")
