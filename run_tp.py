"""Étude de l’énoncé 2 sur l’action Alphabet (GOOGL)."""

import argparse
import csv
import math
from datetime import date
from pathlib import Path
from secrets import randbelow
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter

from asian_pricing import PERIODE, pricer_grille


# Données observées au 31 décembre 2025. Les sources figurent dans le README.
_DATE_VALORISATION = date(2025, 12, 31)
_SPOT = 313.0
_TAUX = 0.0348
_DIVIDENDE = 0.83 / _SPOT
_VOLATILITE = 0.3223020666361277

# Dernière séance de chaque mois. Les trois échéances coïncident avec les
# fixings 6, 12 et 24. Les temps sont calculés en ACT/365F.
_CALENDRIER = (
    "2026-01-30", "2026-02-27", "2026-03-31", "2026-04-30", "2026-05-29", "2026-06-30",
    "2026-07-31", "2026-08-31", "2026-09-30", "2026-10-30", "2026-11-30", "2026-12-31",
    "2027-01-29", "2027-02-26", "2027-03-31", "2027-04-30", "2027-05-28", "2027-06-30",
    "2027-07-30", "2027-08-31", "2027-09-30", "2027-10-29", "2027-11-30", "2027-12-31",
)
_TEMPS_OBSERVATION = tuple(
    (date.fromisoformat(jour) - _DATE_VALORISATION).days / 365 for jour in _CALENDRIER
)
_ECHEANCES = (6, 12, 24)
_FIXINGS_REFERENCE = 12
_STRIKES_RELATIFS = (0.90, 1.00, 1.10)
_PRODUCTION = 50_000
_PILOTE = 5_000
_REPETITIONS = 5
_CIBLE_USD = _SPOT * 5 / 10_000
_SORTIE = Path(__file__).resolve().parent / "resultats"


_TYPES = ("call", "put")
_METHODES = ("naive", "controle")
_MARGE_DIMENSIONNEMENT = 1.10
_MIN_PRODUCTION = 2_000
_MAX_PRODUCTION = 2_000_000


class _Simulations:
    """Enchaîne des sous-flux disjoints à partir d’une même graine."""

    def __init__(self, graine):
        self.graine = graine
        self.prochain = 0

    def __call__(self, nb_fixings, strikes, trajectoires, methode):
        dates = _TEMPS_OBSERVATION[:nb_fixings]
        resultat = pricer_grille(
            _SPOT, strikes, dates[-1], _TAUX, _DIVIDENDE, _VOLATILITE, dates,
            simulations=trajectoires, pilote=_PILOTE, graine=self.graine,
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


def _grille_prix(calculer):
    strikes = [_SPOT * ratio for ratio in _STRIKES_RELATIFS]
    lignes = []
    for nb_fixings in _ECHEANCES:
        contrats = calculer(nb_fixings, strikes, _PRODUCTION, "les_deux")
        for ratio, contrat in zip(_STRIKES_RELATIFS, contrats):
            for type_option in _TYPES:
                option = contrat[type_option]
                lignes.append({
                    "echeance": _CALENDRIER[nb_fixings - 1],
                    "fixings": nb_fixings,
                    "strike": contrat["strike"],
                    "strike_spot": ratio,
                    "type": type_option,
                    "prix_europeen": option["europeenne"],
                    "prix_asiatique_brut": option["naive"]["prix"],
                    "prix_asiatique_controle": option["controle"]["prix"],
                    "demi_ic_brut_usd": _demi_ic(option["naive"]),
                    "demi_ic_controle_usd": _demi_ic(option["controle"]),
                    "trajectoires": _PRODUCTION,
                    "pilote": _PILOTE,
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


def _chronometrer(calculer, tailles, regime, cible=None):
    """Alterne l’ordre des méthodes. Le temps du contrôle inclut le pilote."""
    temps = {methode: [] for methode in _METHODES}
    largeurs = {methode: {t: [] for t in _TYPES} for methode in _METHODES}
    for i in range(_REPETITIONS):
        ordre = _METHODES if i % 2 == 0 else _METHODES[::-1]
        for methode in ordre:
            debut = perf_counter()
            contrat, = calculer(_FIXINGS_REFERENCE, [_SPOT], tailles[methode], methode)
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
            "echeance": _CALENDRIER[_FIXINGS_REFERENCE - 1],
            "strike": _SPOT,
            "trajectoires": tailles[methode],
            "pilote": _PILOTE if methode == "controle" else 0,
            "repetitions": _REPETITIONS,
            "temps_median_ms": median(temps[methode]),
            "demi_ic_call_usd": maxima["call"],
            "demi_ic_put_usd": maxima["put"],
            "demi_ic_max_usd": pire,
            "cible_usd": cible,
            "cible_atteinte": atteinte,
            "graine": calculer.graine,
        })
    return lignes


def _analyser(graine):
    """Produit les prix de la grille et le benchmark à la monnaie à un an."""
    calculer = _Simulations(graine)
    prix = _grille_prix(calculer)

    # Un lot distinct sert à dimensionner les essais avant de les chronométrer.
    taille_echantillon = 30_000
    echantillon, = calculer(_FIXINGS_REFERENCE, [_SPOT], taille_echantillon, "les_deux")
    tailles = _tailles_cibles(echantillon, taille_echantillon, _CIBLE_USD)
    performance = _chronometrer(
        calculer, dict.fromkeys(_METHODES, _PRODUCTION), "trajectoires_egales",
    )
    performance.extend(_chronometrer(calculer, tailles, "precision_cible", _CIBLE_USD))
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sortie", type=Path, default=_SORTIE, help="Dossier des deux CSV.")
    parser.add_argument("--graine", type=int, help="Graine à rejouer (tirée par défaut).")
    args = parser.parse_args()
    graine = randbelow(PERIODE) + 1 if args.graine is None else args.graine

    try:
        print(f"GOOGL · Relevé du {_DATE_VALORISATION} · Graine {graine}", flush=True)
        resultats = _analyser(graine)
        exporter_resultats(resultats, args.sortie)
    except (ValueError, OSError) as erreur:
        parser.error(str(erreur))

    print(f"{len(resultats['prix'])} primes dans prix.csv.")
    print("Benchmark à la monnaie, à un an")
    for ligne in resultats["performance"]:
        regime = "N égal" if ligne["regime"] == "trajectoires_egales" else "Cible"
        methode = "Brut" if ligne["methode"] == "naive" else "Contrôle"
        demi_ic = ligne["demi_ic_max_usd"]
        largeur = "IC indisponible" if demi_ic is None else f"demi-IC max {demi_ic:.4f} USD"
        print(f"{regime:7} · {methode:8} · {ligne['trajectoires']:>6} trajectoires "
              f"· {largeur} · {ligne['temps_median_ms']:.1f} ms")
    print(f"CSV enregistrés dans {args.sortie.resolve()}")


if __name__ == "__main__":
    main()
