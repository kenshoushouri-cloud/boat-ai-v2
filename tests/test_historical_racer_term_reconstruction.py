from research.historical_racer_term_reconstruction_pg import parse_line


def _line():
    x=[" "]*403
    x[0:4]=list("3024")
    x[4:12]=list("西　島　義則".ljust(8))
    x[27:29]=list("広島")
    x[29:31]=list("A1")
    x[48:52]=list("0683")
    x[52:56]=list("0590")
    x[69:72]=list("016")
    return "".join(x)


def test_fixed_width_scaling():
    r=parse_line(_line())
    assert r["racer_number"]==3024
    assert r["racer_class"]==4
    assert r["racer_class_text"]=="A1"
    assert r["national_win_rate"]==6.83
    assert r["national_place2_rate"]==59.0
    assert r["avg_st"]==0.16
