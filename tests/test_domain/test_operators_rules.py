"""Tests for the Operadores panel domain rules (pure, no I/O)."""
from app.domain import operators_rules


def test_aggregate_activity_buckets_by_description():
    # (description, category, appt_count, minutes, pieces)
    rows = [
        ("Produção", "productive", 3, 300, 150),
        ("Setup 1h", "semi_productive", 2, 150, 0),   # padrão 60min cada → 120min, 150 real
        ("Sem Peça", "unproductive", 1, 40, 0),       # categoria improdutivo, mas é espera
        ("Limpeza", "unproductive", 1, 20, 0),
    ]
    act = operators_rules.aggregate_activity(rows)
    assert act.pieces == 150
    assert act.production_hours == 5.0
    assert act.setup_hours == 2.5
    assert act.no_part_hours == round(40 / 60, 2)
    assert act.unproductive_hours == round(20 / 60, 2)
    assert act.setup_standard_min == 120.0   # 60 * 2 apontamentos
    assert act.setup_actual_min == 150.0


def test_setup_productivity_applies_meta_factor():
    rows = [("Setup 1h", "semi_productive", 2, 150, 0)]  # padrão 120, real 150
    act = operators_rules.aggregate_activity(rows)
    # 120 * 0.85 / 150 * 100 = 68.0
    assert operators_rules.setup_productivity(act) == 68.0


def test_setup_productivity_none_without_setup():
    act = operators_rules.aggregate_activity([("Produção", "productive", 1, 60, 10)])
    assert operators_rules.setup_productivity(act) is None


def test_idle_index_excludes_no_part_and_passes_threshold():
    rows = [
        ("Produção", "productive", 1, 540, 100),   # 9h
        ("Sem Peça", "unproductive", 1, 60, 0),    # 1h espera — NÃO entra no numerador
        ("Reunião", "unproductive", 1, 30, 0),     # 0,5h improdutivo
    ]
    act = operators_rules.aggregate_activity(rows)
    # improdutivo 0.5h / total apontado 10.5h = 4.76% ≤ 7% → bonificação
    assert operators_rules.idle_index(act) == 4.76
    assert operators_rules.passes_meritocracy(operators_rules.idle_index(act)) is True


def test_idle_index_above_threshold_fails():
    # 2h improdutivo / 10h = 20%
    rows = [("Produção", "productive", 1, 480, 80), ("Limpeza", "unproductive", 1, 120, 0)]
    act = operators_rules.aggregate_activity(rows)
    assert operators_rules.idle_index(act) == 20.0
    assert operators_rules.passes_meritocracy(operators_rules.idle_index(act)) is False


def test_performance_band():
    assert operators_rules.performance_band(90, 85, 70) == "good"
    assert operators_rules.performance_band(75, 85, 70) == "warn"
    assert operators_rules.performance_band(60, 85, 70) == "bad"


def test_empty_activity_is_all_zero():
    act = operators_rules.aggregate_activity([])
    assert act.reported_hours == 0.0
    assert act.pieces == 0
    assert operators_rules.setup_productivity(act) is None
