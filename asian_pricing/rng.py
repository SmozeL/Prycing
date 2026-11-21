"""Générateur congruentiel 64 bits de L'Ecuyer et normales de Box–Muller."""

import math
from numbers import Integral

import numpy as np


# L'Ecuyer (1999), Table 2, https://doi.org/10.1090/S0025-5718-99-00996-5
_MODULE = 2**64 - 59
_MULTIPLICATEUR = 18_263_440_312_458_789_471
PERIODE = _MODULE - 1
_MAX_UNIFORME = math.nextafter(1.0, 0.0)


def flux_uniformes(graine: int, decalage: int = 0):
    """Fournit les uniformes de la suite congruentielle multiplicative.

    La récurrence entière est xₖ₊₁ = a xₖ mod m, avec uₖ₊₁ = xₖ₊₁/m.
    Pour un décalage h, l'exponentiation modulaire donne directement
    xₕ = aʰ x₀ mod m. Le premier uniforme rendu correspond à xₕ₊₁.
    Des plages disjointes de la même suite servent au pilote, à la
    production et aux répétitions.
    """
    if not isinstance(graine, Integral) or not 0 < graine < _MODULE:
        raise ValueError(f"La graine doit être un entier dans [1, {PERIODE}].")
    if not isinstance(decalage, Integral) or not 0 <= decalage < PERIODE:
        raise ValueError("Le décalage doit être un entier positif ou nul dans la période.")

    etat_initial = int(graine) * pow(_MULTIPLICATEUR, int(decalage), _MODULE) % _MODULE

    def uniforme(etat):
        while True:
            etat = etat * _MULTIPLICATEUR % _MODULE
            valeur = etat / _MODULE
            # Un ratio très proche de 1 peut s'arrondir à 1 en flottant.
            yield valeur if valeur < 1.0 else _MAX_UNIFORME

    return uniforme(etat_initial)


def uniformes_necessaires(nombre_normales: int) -> int:
    """Compte les uniformes par paires, même si la dernière normale est écartée."""
    return nombre_normales + nombre_normales % 2


def normales(flux, nombre: int) -> np.ndarray:
    """Applique la transformée de Box–Muller classique.

    Pour une paire (U₁, U₂), le rayon vaut √(−2 log U₁) et l'angle 2π U₂.
    Les deux coordonnées polaires converties par cos et sin fournissent
    deux normales standard indépendantes sous l'hypothèse d'uniformes
    indépendantes. Une demande impaire utilise une paire supplémentaire et
    écarte sa seconde normale.
    """
    taille = uniformes_necessaires(nombre)
    uniformes = np.fromiter(flux, dtype=float, count=taille)
    rayon = np.sqrt(-2 * np.log(uniformes[::2]))
    angle = 2 * np.pi * uniformes[1::2]
    valeurs = np.empty(taille)
    valeurs[::2] = rayon * np.cos(angle)
    valeurs[1::2] = rayon * np.sin(angle)
    return valeurs[:nombre]
