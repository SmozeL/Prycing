"""Références analytiques du modèle de Black–Scholes."""

import math

import numpy as np
from scipy.special import log_ndtr


def _difference_exponentielles(a: float, b: float) -> float:
    """Calcule exp(a) − exp(b) pour a ≥ b, avec protection des queues."""
    if a <= b:
        return 0.0
    return math.exp(a + math.log(-math.expm1(b - a)))


def prix_lognormal(
    moyenne_log: float, variance_log: float, strike: float, log_actualisation: float,
) -> tuple[float, float]:
    """Prix (call, put) sur une valeur lognormale, payés à l'échéance."""
    log_forward = moyenne_log + variance_log / 2
    log_strike = math.log(strike)
    if variance_log == 0.0:
        return (
            _difference_exponentielles(log_forward + log_actualisation, log_strike + log_actualisation),
            _difference_exponentielles(log_strike + log_actualisation, log_forward + log_actualisation),
        )

    sigma_log = math.sqrt(variance_log)
    d2 = (moyenne_log - log_strike) / sigma_log
    d1 = d2 + sigma_log
    a = log_forward + log_actualisation
    b = log_strike + log_actualisation
    # Calcul direct de l'option hors de la monnaie, puis parité pour l'autre.
    if log_forward <= log_strike:
        call = _difference_exponentielles(a + log_ndtr(d1), b + log_ndtr(d2))
        return call, call + _difference_exponentielles(b, a)
    put = _difference_exponentielles(b + log_ndtr(-d2), a + log_ndtr(-d1))
    return put + _difference_exponentielles(a, b), put


def prix_europeen(
    spot: float, strike: float, maturite: float, taux: float, dividende: float, volatilite: float,
) -> tuple[float, float]:
    """Prix Black–Scholes d'un call et d'un put européens."""
    variance = volatilite**2 * maturite
    moyenne = math.log(spot) + (taux - dividende) * maturite - variance / 2
    return prix_lognormal(moyenne, variance, strike, -taux * maturite)


def moments_geometriques(spot, taux, dividende, volatilite, dates_observation):
    """Moyenne et variance du logarithme de la moyenne géométrique."""
    dates = np.asarray(dates_observation, dtype=float)
    pas = np.diff(dates, prepend=0.0)
    poids = np.arange(dates.size, 0, -1) / dates.size
    # Chaque incrément brownien contribue à tous les fixings suivants.
    variance = volatilite**2 * float(np.dot(poids**2, pas))
    moyenne = math.log(spot) + (taux - dividende - volatilite**2 / 2) * float(dates.mean())
    return moyenne, variance
