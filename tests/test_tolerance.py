from reconciler.tolerance import Tolerance


def test_default_matches_exact():
    t = Tolerance.default()
    assert t.matches(100.0, 100.0)


def test_default_within_absolute():
    t = Tolerance.default()
    assert t.matches(100.0, 100.005)
    assert not t.matches(100.0, 100.02)


def test_default_within_relative():
    t = Tolerance.default()
    big = 1e9
    assert t.matches(big, big * (1 + 1e-7))
    assert not t.matches(big, big * (1 + 1e-5))


def test_zero_baseline_uses_absolute():
    t = Tolerance.default()
    assert t.matches(0.0, 0.005)
    assert not t.matches(0.0, 0.5)


def test_strict_zero_diff_only():
    t = Tolerance.strict()
    assert t.matches(100.0, 100.0)
    assert not t.matches(100.0, 100.000001)


def test_cash_floor_uses_absolute_only():
    t = Tolerance(rel=0.5, abs_=0.01)
    assert not t.cash_floor_violated(0.0)
    assert not t.cash_floor_violated(-0.005)
    assert t.cash_floor_violated(-1.0)
    assert t.cash_floor_violated(-100000.0)
