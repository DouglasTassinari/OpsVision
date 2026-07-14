"""Pure business rules for Compensation (Cargos e Salários) — no database, no UI.

This is the heart of the module, replicated from the origin system's salary
policy. Every function takes plain values (dates, numbers, tuples/dicts) and
returns plain values, so the rules can be unit tested in isolation and reused by
the session working-set (:mod:`app.core.comp_workset`) without a database.

Invariants preserved verbatim from the source module:

1. ``salário = base do nível + adicional de avaliação + ajuste por tempo de casa``.
2. O ajuste por **tempo de casa é acumulativo e FIXO**: cada faixa (2/5/10/15/20
   anos) trava no piso vigente na data do aniversário e nunca mais é reajustada.
3. O piso de um ano só passa a valer em **01/05** (data-base do dissídio); antes
   disso vale o piso do ano anterior.
4. A **bonificação de liderança (10% da base) NÃO faz parte do salário**.
5. No **reajuste coletivo**, o percentual incide só sobre a parcela que não é
   tempo de casa (base + adicionais); o tempo de casa é recomposto sem reajuste,
   exceto a parcela cujo aniversário caiu depois de 01/05 do ano corrente.

Monetary math uses :class:`decimal.Decimal` with ``ROUND_HALF_UP`` and rounds
**each parcel** to two places (not only the final total), matching the origin.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")
FLOOR_CUT_MONTH = 5  # 01/05 — data-base do dissídio
FLOOR_CUT_DAY = 1
DEFAULT_LEADERSHIP_PERCENT = Decimal("10")

# Faixas padrão de tempo de casa: (anos, % sobre o piso vigente). Guia §4.2/§6.1.
DEFAULT_BANDS: tuple[tuple[int, Decimal], ...] = (
    (2, Decimal("5")),
    (5, Decimal("7")),
    (10, Decimal("10")),
    (15, Decimal("12")),
    (20, Decimal("15")),
)

Bands = tuple[tuple[int, Decimal], ...]
Floors = dict[int, Decimal]


def _dec(value) -> Decimal:
    """Coerce anything numeric (int, float, str, Decimal) to Decimal safely."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _money(value) -> Decimal:
    """Round to two decimal places, half-up — applied to every parcel."""
    return _dec(value).quantize(CENTS, rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------- #
# Piso do sindicato                                                           #
# --------------------------------------------------------------------------- #
def floor_for_year(floors: Floors, year: int) -> Decimal:
    """Piso vigente para um ANO: maior piso cadastrado com ano <= ``year``.

    Se nenhum piso for <= ``year`` (aniversário anterior ao primeiro piso
    cadastrado), usa o MENOR piso cadastrado como fallback.
    """
    eligible = [y for y in floors if y <= year]
    reference = max(eligible) if eligible else min(floors)
    return _money(floors[reference])


def effective_floor(floors: Floors, ref: date) -> Decimal:
    """Piso vigente numa DATA, respeitando o corte 01/05.

    O piso de um ano só passa a valer em 01/05; antes disso vale o do ano anterior.
    """
    if (ref.month, ref.day) >= (FLOOR_CUT_MONTH, FLOOR_CUT_DAY):
        year = ref.year
    else:
        year = ref.year - 1
    return floor_for_year(floors, year)


def _anniversary(hire: date, years: int) -> date:
    """Data do aniversário de ``years`` anos de casa (29/02 → 28/02 se preciso)."""
    try:
        return hire.replace(year=hire.year + years)
    except ValueError:  # 29/02 em ano não-bissexto
        return hire.replace(year=hire.year + years, day=28)


# --------------------------------------------------------------------------- #
# Tempo de casa (acumulativo e fixo)                                          #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SeniorityStep:
    """Uma faixa de tempo de casa atingida, com o valor travado no piso do aniversário."""

    years: int
    percent: Decimal
    anniversary: date
    floor: Decimal
    amount: Decimal


def seniority_steps(
    hire: date, ref: date, floors: Floors, bands: Bands = DEFAULT_BANDS
) -> list[SeniorityStep]:
    """Faixas de tempo de casa já atingidas até ``ref``, cada uma travada no piso
    vigente na data do respectivo aniversário."""
    steps: list[SeniorityStep] = []
    for years, percent in bands:
        anniversary = _anniversary(hire, years)
        if anniversary > ref:
            continue  # faixa ainda não atingida
        floor = effective_floor(floors, anniversary)
        amount = _money(_dec(percent) / Decimal(100) * floor)
        steps.append(SeniorityStep(years, _dec(percent), anniversary, floor, amount))
    return steps


def seniority_addon(
    hire: date, ref: date, floors: Floors, bands: Bands = DEFAULT_BANDS
) -> Decimal:
    """Ajuste acumulado por tempo de casa até ``ref`` (soma das faixas atingidas)."""
    total = sum((step.amount for step in seniority_steps(hire, ref, floors, bands)), Decimal(0))
    return _money(total)


# --------------------------------------------------------------------------- #
# Composição do salário                                                       #
# --------------------------------------------------------------------------- #
def evaluation_addon(current_salary, base, seniority) -> Decimal:
    """Adicional de avaliação por diferença: ``max(0, atual − base − tempo de casa)``."""
    residual = _money(current_salary) - _money(base) - _money(seniority)
    return max(Decimal("0.00"), _money(residual))


def compose_salary(base, evaluation, seniority) -> Decimal:
    """Salário = base do nível + adicional de avaliação + tempo de casa."""
    return _money(_money(base) + _money(evaluation) + _money(seniority))


def leadership_bonus(base, percent: Decimal = DEFAULT_LEADERSHIP_PERCENT) -> Decimal:
    """Bonificação de liderança (10% da base). Fora do salário — informativa."""
    return _money(_dec(percent) / Decimal(100) * _money(base))


# --------------------------------------------------------------------------- #
# Simulador (não grava)                                                       #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Simulation:
    base: Decimal
    evaluation_addon: Decimal
    seniority_addon: Decimal
    salary: Decimal
    leadership_bonus: Decimal
    total_with_bonus: Decimal
    steps: list[SeniorityStep]


def simulate(
    base,
    hire: date,
    ref: date,
    floors: Floors,
    *,
    evaluation=Decimal("0"),
    leadership: bool = False,
    bands: Bands = DEFAULT_BANDS,
    current_salary=None,
) -> Simulation:
    """Estima a composição salarial de um cenário, sem gravar nada.

    Se ``current_salary`` for informado, o salário nunca fica abaixo dele
    (``total = max(total, atual)``), como na tela de Gestão do sistema de origem.
    """
    steps = seniority_steps(hire, ref, floors, bands)
    seniority = _money(sum((step.amount for step in steps), Decimal(0)))
    salary = compose_salary(base, evaluation, seniority)
    if current_salary is not None:
        salary = max(salary, _money(current_salary))
    bonus = leadership_bonus(base) if leadership else Decimal("0.00")
    return Simulation(
        base=_money(base),
        evaluation_addon=_money(evaluation),
        seniority_addon=seniority,
        salary=salary,
        leadership_bonus=bonus,
        total_with_bonus=_money(salary + bonus),
        steps=steps,
    )


# --------------------------------------------------------------------------- #
# Reajuste coletivo / dissídio (algoritmo §4.4)                               #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AdjustmentLine:
    key: object  # identificador do colaborador (repassado sem interpretar)
    before: Decimal
    after: Decimal


@dataclass(frozen=True)
class AdjustmentResult:
    year: int
    percent: Decimal
    floor_before: Decimal
    floor_after: Decimal
    floors_after: Floors
    lines: list[AdjustmentLine]
    total_before: Decimal
    total_after: Decimal


def apply_collective_adjustment(
    employees,
    floors: Floors,
    percent,
    year: int,
    ref: date,
    bands: Bands = DEFAULT_BANDS,
) -> AdjustmentResult:
    """Aplica um dissídio de ``percent`` para ``year``, como função pura.

    ``employees``: iterável de ``(key, current_salary, hire_date)``. O percentual
    incide só sobre ``salário − tempo_de_casa`` (base + adicionais); o tempo de
    casa é recomposto — igual, exceto a parcela cujo aniversário caiu depois de
    01/05 do ano corrente, que acompanha o piso novo. Devolve os novos salários e
    o novo piso; quem persiste (na sessão, Fase 2) é o adaptador.
    """
    factor = Decimal(1) + _dec(percent) / Decimal(100)
    floors_before: Floors = {y: _money(v) for y, v in floors.items()}
    floor_before = floor_for_year(floors_before, year)
    floor_after = _money(floor_before * factor)
    floors_after: Floors = dict(floors_before)
    floors_after[year] = floor_after

    lines: list[AdjustmentLine] = []
    total_before = Decimal("0.00")
    total_after = Decimal("0.00")
    for key, salary, hire in employees:
        salary = _money(salary)
        tdc_before = seniority_addon(hire, ref, floors_before, bands)
        tdc_after = seniority_addon(hire, ref, floors_after, bands)
        rest = _money(salary - tdc_before)  # base + adicionais — não é tempo de casa
        after = _money(rest * factor + tdc_after)
        lines.append(AdjustmentLine(key, salary, after))
        total_before += salary
        total_after += after

    return AdjustmentResult(
        year=year,
        percent=_money(percent),
        floor_before=floor_before,
        floor_after=floor_after,
        floors_after=floors_after,
        lines=lines,
        total_before=_money(total_before),
        total_after=_money(total_after),
    )


# --------------------------------------------------------------------------- #
# Defasagem retroativa por dissídio atrasado (§4.5)                           #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class GapLine:
    key: object
    years: int
    percent: Decimal
    anniversary: date
    paid: Decimal
    correct: Decimal
    difference: Decimal


def retroactive_gap(
    employees,
    floors: Floors,
    percent,
    year: int,
    ref: date,
    bands: Bands = DEFAULT_BANDS,
) -> list[GapLine]:
    """Diferença retroativa das faixas de tempo de casa batidas após 01/05 e ainda
    calculadas sobre o piso antigo.

    ``employees``: iterável de ``(key, hire_date)``. Para cada faixa cujo
    aniversário caiu em ``[01/05/year ; ref]``, compara o valor pago (piso antigo)
    com o correto (piso novo = antigo × (1+percent/100)).
    """
    factor = Decimal(1) + _dec(percent) / Decimal(100)
    old_floor = floor_for_year(floors, year)
    new_floor = _money(old_floor * factor)
    window_start = date(year, FLOOR_CUT_MONTH, FLOOR_CUT_DAY)

    lines: list[GapLine] = []
    for key, hire in employees:
        for years, band_percent in bands:
            anniversary = _anniversary(hire, years)
            if window_start <= anniversary <= ref:
                paid = _money(_dec(band_percent) / Decimal(100) * old_floor)
                correct = _money(_dec(band_percent) / Decimal(100) * new_floor)
                lines.append(
                    GapLine(
                        key=key,
                        years=years,
                        percent=_dec(band_percent),
                        anniversary=anniversary,
                        paid=paid,
                        correct=correct,
                        difference=_money(correct - paid),
                    )
                )
    return lines


# --------------------------------------------------------------------------- #
# Permissão de gestão (§8)                                                    #
# --------------------------------------------------------------------------- #
def can_manage(perfil: str | None, areas=None) -> bool:
    """Pode gerenciar se for desenvolvedor/diretor, ou tiver a área 'rh'."""
    if perfil in {"desenvolvedor", "diretor"}:
        return True
    return "rh" in set(areas or [])
