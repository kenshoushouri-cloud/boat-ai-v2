# -*- coding: utf-8 -*-
"""Historical beforeinfo backfill runner with isolated parser v3.

This wrapper monkey-patches only the process executing the historical backfill.
Production realtime collector source is not modified by this file.

Environment variables are the same as backfill_historical_beforeinfo_pg.py:
  HIST_START_DATE / HIST_END_DATE / HIST_WORKERS / HIST_MAX_RACES / ...
"""
from __future__ import annotations

import backfill_historical_beforeinfo_pg as backfill
import historical_beforeinfo_parser_v3 as parser_v3
import v21_realtime_collector_pg as v21

VERSION = "2026-08-22 historical-beforeinfo-backfill-runner-v3"


def main() -> None:
    # backfill_historical_beforeinfo_pg imports the shared v21 module. Patch the
    # in-process function only; no source file or Production service is changed.
    v21.parse_exhibition = parser_v3.parse_exhibition
    backfill.v21.parse_exhibition = parser_v3.parse_exhibition
    print(f"✅ run_historical_beforeinfo_backfill_v3_pg.py VERSION {VERSION}", flush=True)
    print(f"✅ exhibition parser={parser_v3.VERSION}", flush=True)
    backfill.main()


if __name__ == "__main__":
    main()
