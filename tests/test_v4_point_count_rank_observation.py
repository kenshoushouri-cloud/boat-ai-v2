# -*- coding: utf-8 -*-
from pathlib import Path

from research import candidate_discovery_v4_contract as v4


def test_top_five_observation_does_not_change_formal_top_two():
    probs = {
        ticket: float(121 - idx)
        for idx, ticket in enumerate(
            (
                f"{a}-{b}-{c}"
                for a in range(1, 7)
                for b in range(1, 7)
                for c in range(1, 7)
                if len({a, b, c}) == 3
            ),
            1,
        )
    }
    top2 = v4.top_tickets(probs, v4.CORE_TICKETS)
    top5 = v4.top_tickets(probs, v4.RESEARCH_TICKET_RANKS)
    assert v4.CORE_TICKETS == 2
    assert v4.RESEARCH_TICKET_RANKS == 5
    assert top5[:2] == top2
    assert len(top5) == 5


def test_main_feed_keeps_research_ranks_outside_formal_tickets():
    source = (
        Path(__file__).resolve().parents[1]
        / ".github/scripts/candidate_discovery_v4_main_feed_pg.py"
    ).read_text(encoding="utf-8")
    assert '"research_ranked_tickets"' in source
    assert '"tickets": tickets' in source
    assert "v4.RESEARCH_TICKET_RANKS" in source


def test_research_rank_observation_has_no_new_selection_constant():
    assert v4.CORE_RACES == 6
    assert v4.CORE_TICKETS == 2
