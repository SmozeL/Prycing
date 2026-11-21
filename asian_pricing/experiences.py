"""Grille de prix et mesure du gain apporté par le contrôle géométrique."""

import csv
import math
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter

from .pricer import pricer_grille


_TYPES = ("call", "put")
_METHODES = ("naive", "controle")
_MARGE_DIMENSIONNEMENT = 1.10
_MIN_PRODUCTION = 1_024
_MAX_PRODUCTION = 2_000_000


class _Simulations:
    """Enchaîne des sous-flux disjoints à partir d’une même graine."""

    def __init__(self, spot, graine, pilote):
        self.spot = spot
        self.graine = graine
        self.pilote = pilote
        self.prochain = 0

    def __call__(self, echeance, strikes, trajectoires, methode):
        resultat = pricer_grille(
            self.spot, strikes, echeance["maturite"], echeance["taux"],
            echeance["dividende"], echeance["volatilite"], echeance["dates_observation"],
            simulations=trajectoires, pilote=self.pilote, graine=self.graine,
            decalage=self.prochain, methode=methode,
        )
        self.prochain += resultat["uniformes_reserves"]
        return resultat["strikes"]


def _demi_ic(estimation):
    intervalle = estimation["ic"]
    if intervalle is None:
        return None
    bas, haut = intervalle
    return (haut - bas) / 2


def _grille_prix(calculer, echeances, ratios, simulations):
    strikes = [calculer.spot * ratio for ratio in ratios]
    lignes = []
    for echeance in echeances:
        contrats = calculer(echeance, strikes, simulations, "les_deux")
        for ratio, contrat in zip(ratios, contrats):
            for type_option in _TYPES:
                option = contrat[type_option]
                lignes.append({
                    "echeance": echeance["date"],
                    "fixings": len(echeance["dates_observation"]),
                    "strike": contrat["strike"],
                    "strike_spot": ratio,
                    "type": type_option,
                    "prix_europeen": option["europeenne"],
                    "prix_asiatique_brut": option["naive"]["prix"],
                    "prix_asiatique_controle": option["controle"]["prix"],
                    "demi_ic_brut_usd": _demi_ic(option["naive"]),
                    "demi_ic_controle_usd": _demi_ic(option["controle"]),
                    "trajectoires": simulations,
                    "pilote": calculer.pilote,
                    "graine": calculer.graine,
                })
    return lignes


def _tailles_cibles(echantillon, taille_echantillon, cible):
    """Dimensionne N grâce à la décroissance de la demi-largeur en 1/√N.

    Pour chaque méthode, on retient la plus grande demi-largeur des deux
    payoffs et on ajoute 10 % de trajectoires pour tenir compte de son
    estimation par échantillonnage.
    """
    tailles = {}
    for methode in _METHODES:
        largeurs = [_demi_ic(echantillon[t][methode]) for t in _TYPES]
        if None in largeurs:
            tailles[methode] = _MAX_PRODUCTION
            continue
        n = math.ceil(_MARGE_DIMENSIONNEMENT * taille_echantillon * (max(largeurs) / cible)**2)
        tailles[methode] = min(_MAX_PRODUCTION, max(_MIN_PRODUCTION, n))
    return tailles


def _chronometrer(calculer, echeance, tailles, repetitions, regime, cible=None):
    """Alterne l’ordre des méthodes. Le temps du contrôle inclut le pilote."""
    temps = {methode: [] for methode in _METHODES}
    largeurs = {methode: {t: [] for t in _TYPES} for methode in _METHODES}
    for i in range(repetitions):
        ordre = _METHODES if i % 2 == 0 else _METHODES[::-1]
        for methode in ordre:
            debut = perf_counter()
            contrat, = calculer(echeance, [calculer.spot], tailles[methode], methode)
            temps[methode].append((perf_counter() - debut) * 1_000)
            for type_option in _TYPES:
                largeurs[methode][type_option].append(_demi_ic(contrat[type_option][methode]))

    lignes = []
    for methode in _METHODES:
        maxima = {
            type_option: None if None in valeurs else max(valeurs)
            for type_option, valeurs in largeurs[methode].items()
        }
        pire = None if None in maxima.values() else max(maxima.values())
        atteinte = None if cible is None else pire is not None and pire <= cible
        lignes.append({
            "regime": regime,
            "methode": methode,
            "echeance": echeance["date"],
            "strike": calculer.spot,
            "trajectoires": tailles[methode],
            "pilote": calculer.pilote if methode == "controle" else 0,
            "repetitions": repetitions,
            "temps_median_ms": median(temps[methode]),
            "demi_ic_call_usd": maxima["call"],
            "demi_ic_put_usd": maxima["put"],
            "demi_ic_max_usd": pire,
            "cible_usd": cible,
            "cible_atteinte": atteinte,
            "graine": calculer.graine,
        })
    return lignes


def analyser_marche(marche, *, graine=2026, simulations=50_000, pilote=5_000, repetitions=5):
    """Produit les prix de la grille et le benchmark au strike égal au spot."""
    if min(simulations, pilote) < 2 or repetitions < 1:
        raise ValueError("Il faut au moins deux trajectoires et une répétition.")

    actif, = marche["actifs"]
    echeances = sorted(actif["echeances"], key=lambda e: e["date"])
    reference = min(echeances, key=lambda e: abs(e["maturite"] - 1))
    calculer = _Simulations(actif["spot"], graine, pilote)
    prix = _grille_prix(calculer, echeances, marche["strike_ratios"], simulations)

    # Cette simulation dimensionne les essais ciblés avec un lot distinct.
    cible = actif["spot"] * marche["cible_precision_pb"] / 10_000
    taille_echantillon = 30_000
    echantillon, = calculer(reference, [actif["spot"]], taille_echantillon, "les_deux")
    tailles = _tailles_cibles(echantillon, taille_echantillon, cible)
    performance = _chronometrer(
        calculer, reference, dict.fromkeys(_METHODES, simulations),
        repetitions, "trajectoires_egales",
    )
    performance.extend(_chronometrer(
        calculer, reference, tailles, repetitions, "precision_cible", cible,
    ))
    return {"prix": prix, "performance": performance}


def exporter_resultats(resultats, dossier):
    """Prépare les deux CSV avant de remplacer les fichiers de sortie."""
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=dossier) as temporaire:
        fichiers = []
        for nom, lignes in resultats.items():
            chemin = Path(temporaire) / f"{nom}.csv"
            with chemin.open("w", newline="", encoding="utf-8") as fichier:
                writer = csv.DictWriter(fichier, fieldnames=list(lignes[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(lignes)
            fichiers.append(chemin)
        for chemin in fichiers:
            chemin.replace(dossier / chemin.name)
