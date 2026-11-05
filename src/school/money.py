"""Exact decimal scenario units; solver rows use integer cost multiples."""

from decimal import Decimal
from functools import reduce
from math import gcd


def amount(value):
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError("money must be finite and non-negative")
    return result


def budget_amount(state):
    exact = getattr(state, "remaining_budget_exact", None)
    # A dataclasses.replace override of the public budget must remain effective.
    if exact is not None and float(exact) == state.remaining_budget:
        return amount(exact)
    return amount(state.remaining_budget)


def programme_cost(price):
    return 5 * amount(price)


def integer_costs(costs, budget):
    """Divide exact decimal costs by their GCD and floor the budget accordingly.

    Flooring is exact because every feasible expenditure is a multiple of that
    GCD. This avoids solver feasibility tolerances admitting tiny overspending.
    """
    values = [amount(cost) for cost in costs]
    budget = amount(budget)
    places = max((max(0, -v.as_tuple().exponent) for v in [*values, budget]), default=0)
    scale = 10 ** places
    integers = [int(v * scale) for v in values]
    divisor = reduce(gcd, integers, 0) or 1
    coefficients = [v // divisor for v in integers]
    upper = int(budget * scale) // divisor
    # All selected costs must be exactly representable by the MILP's doubles.
    if any(v > 2 ** 50 for v in coefficients):
        raise ValueError("monetary coefficient range exceeds exact solver precision")
    return coefficients, min(upper, sum(coefficients))
