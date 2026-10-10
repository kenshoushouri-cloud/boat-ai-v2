# -*- coding: utf-8 -*-
"""Only fake network; no GitHub Actions step touches boatrace.jp."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from v5.official_start_status_observation_pilot import (
    MAX_TOTAL_GETS, ObservationNotApproved, bounded_observation_spec,
    run_bounded_official_observation,
)
from v5_beforeinfo_test_fixtures import six_boat_html
from test_v5_official_racelist_readback import make_html

R1 = "20261010_09_04"
R2 = "20261010_09_05"
R3 = "20261010_09_06"
DAY = datetime(2026, 10, 10, 2, 50, 0, tzinfo=timezone.utc)
BEFORE = "https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno=4&jcd=09&hd=20261010"


class HTTPResponse:
    def __init__(self, url, body, status=200, redirect_history=None, size=None):
        self.url=url
        self.status_code=status
        self.chunks=[body]
        self.history=[] if redirect_history is None else redirect_history
        self.headers={"Content-Length":str(len(body) if size is None else size)}
        self.closed=False

    def iter_content(self, *, chunk_size):
        for chunk in self.chunks:
            yield chunk

    def close(self):
        self.closed=True


class NoNetworkFake:
    def __init__(self, *, status=200, fail_at=None, redirect_at=None,
                 wrong_url_at=None, too_large_at=None, body_override=None):
        self.calls=[]
        self.replies=[]
        self.status=status
        self.fail_at=fail_at
        self.redirect_at=redirect_at
        self.wrong_url_at=wrong_url_at
        self.too_large_at=too_large_at
        self.body_override=body_override

    def get(self, url, **kw):
        self.calls.append((url,kw))
        n=len(self.calls)
        if self.fail_at==n:
            raise TimeoutError("simulated transport timeout: no real outbound")
        body=(
            self.body_override if self.body_override is not None else
            six_boat_html() if "/beforeinfo?" in url else make_html()
        )
        r=HTTPResponse(
            url if self.wrong_url_at!=n else "https://invalid.example/redirect",
            body, status=self.status,
            redirect_history=[{"status_code":301}] if self.redirect_at==n else None,
            size=999_999_999 if self.too_large_at==n else None,
        )
        self.replies.append(r)
        return r


def run(*, races=None, fake=None, approved=True, clock=None):
    fake=NoNetworkFake() if fake is None else fake
    return run_bounded_official_observation(
        race_ids=[R1] if races is None else races,
        session=fake,
        external_get_approved=approved,
        clock=(lambda: DAY) if clock is None else clock,
    )


class TestV5StartStatusObservationPilot(unittest.TestCase):
    def denied(self, code, *, fake=None, **kw):
        fake=NoNetworkFake() if fake is None else fake
        with self.assertRaises(ObservationNotApproved) as err:
            run(fake=fake, **kw)
        self.assertEqual(str(err.exception),code)
        self.assertEqual(len(fake.calls),0)

    def test_no_implicit_network_even_given_valid_session(self):
        self.denied("OFF_BY_DEFAULT_MANUAL_SCOPE_REQUIRED",approved=False)

    def test_spec_exact_two_official_endpoints_one_race(self):
        spec=bounded_observation_spec([R1])
        self.assertEqual(len(spec),2)
        self.assertEqual([x[1] for x in spec],
                         ["official_racelist","official_beforeinfo"])
        self.assertTrue(spec[0][2].startswith("https://www.boatrace.jp/"))
        self.assertEqual(spec[1][2],BEFORE)

    def test_two_races_max_four_urls_same_day(self):
        spec=bounded_observation_spec([R1,R2])
        self.assertEqual(len(spec),4)
        self.assertEqual(len(set(x[2] for x in spec)),4)

    def test_three_races_rejected(self):
        self.denied("ONE_OR_TWO_DISTINCT_RACES_REQUIRED",races=[R1,R2,R3])

    def test_empty_race_ids_rejected(self):
        self.denied("ONE_OR_TWO_DISTINCT_RACES_REQUIRED",races=[])

    def test_duplicate_ids_rejected(self):
        self.denied("ONE_OR_TWO_DISTINCT_RACES_REQUIRED",races=[R1,R1])

    def test_invalid_race_no_rejected(self):
        self.denied("INVALID_RACE_ID",races=["20261010_09_13"])

    def test_invalid_venue_rejected(self):
        self.denied("INVALID_RACE_ID",races=["20261010_25_04"])

    def test_invalid_calendar_date_rejected(self):
        self.denied("INVALID_CALENDAR_DATE",races=["20260231_09_04"])

    def test_cross_day_probes_disallowed(self):
        self.denied("ONLY_ONE_RACE_DAY_PER_PILOT",
                    races=[R1,"20261011_09_04"])

    def test_observation_day_mismatch_no_get(self):
        self.denied("RACE_DAY_MUST_EQUAL_JST_OBSERVATION_DAY",
                    clock=lambda: datetime(2026,10,9,tzinfo=timezone.utc))

    def test_naive_clock_cannot_be_used(self):
        self.denied("UNVERIFIED_OBSERVATION_CLOCK",
                    clock=lambda:datetime(2026,10,10,11,50))

    def test_missing_session_does_not_make_get(self):
        with self.assertRaisesRegex(
            ObservationNotApproved,"EXPLICIT_HTTP_SESSION_REQUIRED"
        ):
            run_bounded_official_observation(
                race_ids=[R1],session=object(),external_get_approved=True,
                clock=lambda:DAY,
            )

    def test_complete_two_source_probe_has_no_raw_data_persistence(self):
        fake=NoNetworkFake()
        summary=run(fake=fake)
        self.assertEqual(summary["status"],"READ_ONLY_DISCOVERY_COMPLETE_NOT_VERIFIED")
        self.assertEqual(summary["attempted_gets"],2)
        self.assertEqual(summary["max_gets"],MAX_TOTAL_GETS)
        self.assertEqual(len(summary["observations"]),2)
        self.assertTrue(all(x.closed for x in fake.replies))
        self.assertTrue(all(x[1] == {"allow_redirects":False,
                                      "stream":True,"timeout":12.0}
                            for x in fake.calls))
        self.assertFalse(summary["persistence_performed"])
        self.assertFalse(summary["all_six_active_confirmed"])
        self.assertFalse(summary["forward_eligible"])
        self.assertTrue(all(v["first_observed_at"] is None
                            for v in summary["observations"]))
        self.assertTrue(all(v["raw_sha256"] and v["raw_size_bytes"]>0
                            for v in summary["observations"]))
        text=str(summary)
        self.assertNotIn("選手1",text)
        self.assertNotIn("1001",text)
        self.assertNotIn("raw_base64",text)
        self.assertNotIn("first_write_confirmed",text)

    def test_two_races_fully_bounded_four_gets(self):
        fake=NoNetworkFake()
        result=run(fake=fake,races=[R1,R2])
        self.assertEqual(result["attempted_gets"],4)
        self.assertEqual(len(fake.calls),4)
        self.assertEqual(len(result["observations"]),4)
        self.assertFalse(result["forward_eligible"])

    def test_candidate_label_is_not_positive_start_proof(self):
        page=six_boat_html().replace(
            b"</body>",
            "<th>出走確定</th><th>出走状況</th></body>".encode("utf-8"),
        )
        result=run(fake=NoNetworkFake(body_override=page))
        before=result["observations"][1]
        self.assertEqual(before["hints"]["potential_status_labels"]["出走確定"],1)
        self.assertFalse(before["all_six_active_confirmed"])
        self.assertFalse(result["forward_eligible"])

    def test_no_markup_six_starters_never_proven(self):
        result=run(fake=NoNetworkFake())
        self.assertTrue(all(not x["all_six_active_confirmed"]
                            for x in result["observations"]))
        self.assertEqual(result["observations"][1]["hints"]["html_parse"],
                         "LABEL_COUNTS_ONLY")

    def test_html_with_invalid_charset_only_unknown(self):
        fake=NoNetworkFake(body_override=b"\xff\xfdgarbled")
        result=run(fake=fake)
        self.assertEqual(result["observations"][0]["hints"]["html_parse"],
                         "UNKNOWN_CHARSET")
        self.assertFalse(result["forward_eligible"])

    def test_transport_timeout_stops_at_first_get_no_retry(self):
        fake=NoNetworkFake(fail_at=1)
        result=run(fake=fake,races=[R1,R2])
        self.assertEqual(result["status"],"INCOMPLETE_STOPPED")
        self.assertEqual(result["attempted_gets"],1)
        self.assertEqual(len(fake.calls),1)
        self.assertFalse(result["persistence_performed"])

    def test_http_error_stops_without_retry_or_next_source(self):
        fake=NoNetworkFake(status=503)
        result=run(fake=fake)
        self.assertEqual(result["status"],"INCOMPLETE_STOPPED")
        self.assertEqual(result["attempted_gets"],1)
        self.assertEqual(len(fake.calls),1)
        self.assertTrue(fake.replies[0].closed)

    def test_redirect_history_fails_closed(self):
        fake=NoNetworkFake(redirect_at=1)
        result=run(fake=fake)
        self.assertEqual(result["status"],"INCOMPLETE_STOPPED")
        self.assertEqual(len(fake.calls),1)

    def test_redirected_host_fails_closed(self):
        fake=NoNetworkFake(wrong_url_at=1)
        result=run(fake=fake)
        self.assertEqual(result["status"],"INCOMPLETE_STOPPED")
        self.assertEqual(len(fake.calls),1)

    def test_advertised_large_response_not_downloaded(self):
        fake=NoNetworkFake(too_large_at=1)
        result=run(fake=fake)
        self.assertEqual(result["status"],"INCOMPLETE_STOPPED")
        self.assertTrue(fake.replies[0].closed)
        self.assertEqual(len(fake.calls),1)

    def test_second_source_failure_no_third_get(self):
        fake=NoNetworkFake(fail_at=2)
        result=run(fake=fake,races=[R1,R2])
        self.assertEqual(result["status"],"INCOMPLETE_STOPPED")
        self.assertEqual(result["attempted_gets"],2)
        self.assertEqual(len(fake.calls),2)
        self.assertEqual(len(result["observations"]),1)
        self.assertFalse(result["forward_eligible"])


if __name__=="__main__":
    unittest.main()
