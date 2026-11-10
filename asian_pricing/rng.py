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
    """Fournit les uniformes sur ]0,1[ en sautant les premiers états."""
    if not isinstance(graine, Integral) or not 0 < graine < _MODULE:
        raise ValueError(f"La graine doit être un entier dans [1, {PERIODE}].")
    if not isinstance(decalage, Integral) or not 0 <= decalage < PERIODE:
        raise ValueError("Le décalage doit être un entier positif ou nul dans la période.")

    etat_initial = int(graine) * pow(_MULTIPLICATEUR, int(decalage), _MODULE) % _MODULE

    def uniforme(etat):
        while True:
            etat = etat * _MULTIPLICATEUR % _MODULE
            valeur = etat / _MODULE
            yield valeur if valeur < 1.0 else _MAX_UNIFORME

    return uniforme(etat_initial)


def uniformes_necessaires(nombre_normales: int) -> int:
    """Nombre d'uniformes tirées pour un lot de Box–Muller."""
    return nombre_normales + nombre_normales % 2


def normales(flux, nombre: int) -> np.ndarray:
    """Transforme une paire d'uniformes en deux normales standard."""
    taille = uniformes_necessaires(nombre)
    uniformes = np.fromiter(flux, dtype=float, count=taille)
    rayon = np.sqrt(-2 * np.log(uniformes[::2]))
    angle = 2 * np.pi * uniformes[1::2]
    valeurs = np.empty(taille)
    valeurs[::2] = rayon * np.cos(angle)
    valeurs[1::2] = rayon * np.sin(angle)
    return valeurs[:nombre]
