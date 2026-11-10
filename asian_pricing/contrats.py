"""Conventions et validation des paramètres du contrat."""

import math

import numpy as np


def dates_regulieres(maturite: float, frequence: float) -> np.ndarray:
    """Construit les observations iT/m, avec m = ceil(fréquence × T)."""
    cible = maturite * frequence
    if not math.isfinite(cible) or cible <= 0:
        raise ValueError("La maturité et la fréquence doivent définir un nombre d'observations positif.")
    entier = round(cible)
    # Une erreur d'un ulp ne doit pas créer un fixing supplémentaire.
    if math.isclose(cible, entier, rel_tol=0.0, abs_tol=math.ulp(cible)):
        cible = entier
    return np.linspace(0.0, maturite, max(1, math.ceil(cible)) + 1)[1:]


def valider_contrat(spot, strikes, maturite, taux, dividende, volatilite, dates_observation):
    """Vérifie les paramètres du modèle et le calendrier exprimé en années."""
    if not all(math.isfinite(x) for x in (spot, maturite, taux, dividende, volatilite)):
        raise ValueError("Les paramètres financiers doivent être finis.")
    if spot <= 0 or maturite <= 0 or volatilite < 0:
        raise ValueError("Spot et maturité doivent être positifs, volatilité positive ou nulle.")

    prix_exercice = np.asarray(strikes, dtype=float)
    if (
        prix_exercice.ndim != 1 or not prix_exercice.size
        or not np.all(np.isfinite(prix_exercice)) or np.any(prix_exercice <= 0)
    ):
        raise ValueError("Fournir une liste non vide de strikes finis et strictement positifs.")

    dates = np.asarray(dates_observation, dtype=float)
    if (
        dates.ndim != 1 or not dates.size
        or not np.all(np.isfinite(dates))
        or dates[0] <= 0 or dates[-1] > maturite
        or np.any(np.diff(dates) <= 0)
    ):
        raise ValueError("Les dates d'observation doivent être strictement croissantes dans ]0, T].")
    return prix_exercice, dates
