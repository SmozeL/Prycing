"""Références analytiques du modèle de Black–Scholes."""

import math

import numpy as np
from scipy.special import log_ndtr


def _difference_exponentielles(a: float, b: float) -> float:
    """Calcule une différence théoriquement positive de termes exponentiels.

    La factorisation exp(a) × (1 − exp(b − a)) évite une soustraction de
    termes proches. `expm1` évalue le second facteur avec précision et la
    recombinaison en logarithmes conserve les petites primes.
    """
    if a <= b:
        return 0.0
    return math.exp(a + math.log(-math.expm1(b - a)))


def prix_lognormal(
    moyenne_log: float, variance_log: float, strike: float, log_actualisation: float,
) -> tuple[float, float]:
    """Prix du call et du put sur Z pour log Z distribué selon N(μ, v).

    F = E[Z] = exp(μ + v/2). Pour v > 0, les termes de la formule de
    Black–Scholes sont gouvernés par d₂ = (μ − log K)/√v et d₁ = d₂ + √v.
    Le call vaut exp(−rT) [F Φ(d₁) − K Φ(d₂)]. La parité donne
    call − put = exp(−rT) (F − K). Le paiement est actualisé depuis T.
    Pour v = 0, Z est connu et on actualise directement le payoff.
    """
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
    # Calcul direct de l'option hors de la monnaie par rapport à F, puis
    # ajout de la valeur intrinsèque actualisée pour l'autre jambe.
    # log_ndtr évalue log Φ de manière stable jusque dans les queues.
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
    """Moyenne μ et variance v de log G pour les m dates fournies.

    log G est la moyenne des log S(t_j). Sa partie déterministe vaut
    μ = log S₀ + (r − q − σ²/2) × moyenne(t_j). Dans la partie brownienne,
    ΔW_i intervient dans W(t_i), …, W(t_m). Il figure donc dans m − i + 1
    des m observations et son poids est w_i = (m − i + 1)/m.
    Les incréments sont indépendants et Var(ΔW_i) = Δt_i. On obtient
    v = σ² Σ_i w_i² Δt_i, forme équivalente à la somme des covariances
    σ² Σ_i Σ_j min(t_i, t_j)/m².
    """
    dates = np.asarray(dates_observation, dtype=float)
    pas = np.diff(dates, prepend=0.0)
    poids = np.arange(dates.size, 0, -1) / dates.size
    variance = volatilite**2 * float(np.dot(poids**2, pas))
    moyenne = math.log(spot) + (taux - dividende - volatilite**2 / 2) * float(dates.mean())
    return moyenne, variance
