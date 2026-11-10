"""Calibration reproductible du relevé Cboe PM du 30 octobre 2026.

L'étude lit uniquement le petit instantané dérivé. La reconstruction s'exécute
séparément avec python -m asian_pricing.donnees --csv-dir <archive locale>.
"""

import argparse
import calendar
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtr


DATE_VALORISATION = date(2026, 10, 30)
HEURE_RELEVE = datetime.combine(
    DATE_VALORISATION, time(16), tzinfo=ZoneInfo("America/New_York"),
)
ECHEANCES = (date(2027, 1, 29), date(2027, 3, 31), date(2027, 6, 30))
RACINES = {"SPX": "SPXW", "RUT": "RUTW"}
INSTANTANE = Path(__file__).resolve().parents[1] / "data" / "market_snapshot.json"
DUREE_HISTORIQUE = 252
ANCIENNETE_MAX_SECONDES = 60
SPREAD_RELATIF_MAX = 0.15
FENETRE_SPOT = 0.05
FENETRE_FORWARD = 0.015
STRIKES_CALIBRATION = 3
# Seule fermeture fériée sur une fin de mois pendant la période étudiée.
FERMETURES_FIN_DE_MOIS = frozenset((date(2027, 5, 31),))
SOURCES = {
    "eom_marking_prices_list.csv": (
        "https://cdn.cboe.com/resources/marking_prices/eom_marking_prices_list.csv"
    ),
    "SPX_History.csv": "https://cdn.cboe.com/api/global/us_indices/daily_prices/SPX_History.csv",
    "RUT_History.csv": "https://cdn.cboe.com/api/global/us_indices/daily_prices/RUT_History.csv",
    "feds200628.csv": "https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv",
}
DOCUMENTATION = {
    "cotations": (
        "https://www.cboe.com/markets/us/options/market-statistics/"
        "product-data/proprietary-index-marking-prices/"
    ),
    "calendrier": "https://www.cboe.com/about/hours/us-options/",
    "courbe": "https://www.federalreserve.gov/data/nominal-yield-curve.htm",
}


@dataclass(frozen=True)
class Fourchette:
    bid: float
    ask: float

    @property
    def milieu(self):
        return (self.bid + self.ask) / 2

    @property
    def spread_relatif(self):
        return (self.ask - self.bid) / self.milieu


@dataclass(frozen=True)
class Paire:
    strike: float
    call: Fourchette
    put: Fourchette


def charger_marche(chemin=None):
    """Charge l'instantané dérivé sans requête réseau."""
    chemin = INSTANTANE if chemin is None else Path(chemin)
    with chemin.open(encoding="utf-8") as fichier:
        return json.load(fichier)


def annee_act365(debut, fin):
    return (fin - debut).days / 365.0


def fixings_mensuels(echeance):
    """Dernière clôture de chaque mois, puis échéance, pour le relevé retenu."""
    dates = []
    annee, mois = DATE_VALORISATION.year, DATE_VALORISATION.month
    while (annee, mois) < (echeance.year, echeance.month):
        if mois == 12:
            annee, mois = annee + 1, 1
        else:
            mois += 1
        if (annee, mois) == (echeance.year, echeance.month):
            break
        dernier = date(annee, mois, calendar.monthrange(annee, mois)[1])
        while dernier.weekday() >= 5 or dernier in FERMETURES_FIN_DE_MOIS:
            dernier -= timedelta(days=1)
        dates.append(dernier)
    return dates + [echeance]


def _clotures(chemin, symbole):
    with chemin.open(newline="", encoding="utf-8-sig") as fichier:
        observations = {}
        for ligne in csv.DictReader(fichier):
            jour = datetime.strptime(ligne["DATE"], "%m/%d/%Y").date()
            if jour <= DATE_VALORISATION:
                observations[jour] = float(ligne[symbole])
    if DATE_VALORISATION not in observations or len(observations) <= DUREE_HISTORIQUE:
        raise ValueError(f"Historique insuffisant pour {symbole} au {DATE_VALORISATION}.")
    jours = sorted(observations)[-DUREE_HISTORIQUE - 1:]
    cours = np.array([observations[jour] for jour in jours])
    if not np.all(np.isfinite(cours) & (cours > 0)):
        raise ValueError(f"Clôtures invalides pour {symbole}.")
    rendements = np.diff(np.log(cours))
    volatilite = np.std(rendements, ddof=1) * math.sqrt(DUREE_HISTORIQUE)
    return float(cours[-1]), float(volatilite), jours[0]


def _parametres_fed(chemin):
    with chemin.open(newline="", encoding="utf-8-sig") as fichier:
        for ligne in fichier:
            if ligne.startswith("Date,"):
                entetes = next(csv.reader([ligne]))
                break
        else:
            raise ValueError("Entête de la courbe Fed introuvable.")
        for ligne in csv.DictReader(fichier, fieldnames=entetes):
            if ligne["Date"] == DATE_VALORISATION.isoformat():
                colonnes = ("BETA0", "BETA1", "BETA2", "BETA3", "TAU1", "TAU2")
                return {nom: float(ligne[nom]) for nom in colonnes}
    raise ValueError(f"Courbe Fed introuvable au {DATE_VALORISATION}.")


def taux_zero_coupon(parametres, maturite):
    """Taux continu Svensson à la maturité ACT/365F, exprimé en décimal."""
    x1 = maturite / parametres["TAU1"]
    x2 = maturite / parametres["TAU2"]
    charge1 = -math.expm1(-x1) / x1
    charge2 = -math.expm1(-x2) / x2
    return (
        parametres["BETA0"]
        + parametres["BETA1"] * charge1
        + parametres["BETA2"] * (charge1 - math.exp(-x1))
        + parametres["BETA3"] * (charge2 - math.exp(-x2))
    ) / 100.0


def _fourchette_fraiche(ligne, cote):
    try:
        horodatage = datetime.fromisoformat(ligne[f"{cote}_message_time"])
        bid = float(ligne[f"{cote}_last_disseminated_market_bid"])
        ask = float(ligne[f"{cote}_last_disseminated_market_ask"])
    except (TypeError, ValueError):
        return None
    if horodatage.tzinfo is None:
        return None
    age = (HEURE_RELEVE - horodatage).total_seconds()
    if not (0 <= age <= ANCIENNETE_MAX_SECONDES and 0 < bid <= ask < math.inf):
        return None
    fourchette = Fourchette(bid, ask)
    return fourchette if fourchette.spread_relatif <= SPREAD_RELATIF_MAX else None


def _paires_cboe(chemin):
    paires = {
        (racine, jour.isoformat()): []
        for racine in RACINES.values() for jour in ECHEANCES
    }
    with chemin.open(newline="", encoding="utf-8-sig") as fichier:
        for ligne in csv.DictReader(fichier):
            cle = (ligne["root"], ligne["expiry"])
            if cle in paires:
                call = _fourchette_fraiche(ligne, "call")
                put = _fourchette_fraiche(ligne, "put")
                if call is not None and put is not None:
                    strike = float(ligne["strike"])
                    if not (0 < strike < math.inf):
                        raise ValueError(f"Strike invalide pour {cle}.")
                    paires[cle].append(Paire(strike, call, put))
    for cle, valeurs in paires.items():
        if not valeurs:
            raise ValueError(
                f"Aucune paire Cboe exploitable pour {cle} au {DATE_VALORISATION}. "
                "Le fichier de fin de mois a peut-être été remplacé. "
                "Utiliser l'archive locale du relevé demandé."
            )
        if len({paire.strike for paire in valeurs}) != len(valeurs):
            raise ValueError(f"Strikes en double dans le relevé pour {cle}.")
    return paires


def _prix_vanille(forward, strike, actualisation, volatilite, maturite, est_call):
    variance = volatilite * volatilite * maturite
    if variance == 0:
        return actualisation * max(forward - strike if est_call else strike - forward, 0.0)
    ecart_type = math.sqrt(variance)
    d1 = (math.log(forward / strike) + variance / 2) / ecart_type
    d2 = d1 - ecart_type
    if est_call:
        return actualisation * (forward * ndtr(d1) - strike * ndtr(d2))
    return actualisation * (strike * ndtr(-d2) - forward * ndtr(-d1))


def _volatilite_implicite(prix, forward, strike, actualisation, maturite, est_call):
    borne_basse = _prix_vanille(forward, strike, actualisation, 0.0, maturite, est_call)
    borne_haute = actualisation * (forward if est_call else strike)
    if not borne_basse < prix < borne_haute:
        raise ValueError(f"Prix européen hors bornes pour K={strike:g}.")
    return brentq(
        lambda sigma: _prix_vanille(
            forward, strike, actualisation, sigma, maturite, est_call,
        ) - prix,
        0.0, 5.0,
    )


def _forward_indicatif(paire, actualisation):
    return paire.strike + (paire.call.milieu - paire.put.milieu) / actualisation


def _calibrer(paires, spot, taux, maturite):
    """Forward de parité et volatilité unique estimée près du forward."""
    actualisation = math.exp(-taux * maturite)
    proches_spot = [p for p in paires if abs(p.strike / spot - 1.0) <= FENETRE_SPOT]
    if not proches_spot:
        raise ValueError("Aucune paire call-put proche du spot.")
    premier_forward = median(_forward_indicatif(p, actualisation) for p in proches_spot)
    retenues = [
        p for p in proches_spot if abs(p.strike / premier_forward - 1.0) <= FENETRE_FORWARD
    ]
    if len(retenues) <= STRIKES_CALIBRATION:
        raise ValueError("Trop peu de paires pour estimer puis contrôler la volatilité.")

    bas = max(
        p.strike + (p.call.bid - p.put.ask) / actualisation for p in retenues
    )
    haut = min(
        p.strike + (p.call.ask - p.put.bid) / actualisation for p in retenues
    )
    if not 0 < bas <= haut:
        raise ValueError("Les fourchettes de parité ne donnent aucun forward commun positif.")
    milieu = median(_forward_indicatif(p, actualisation) for p in retenues)
    forward = min(max(milieu, bas), haut)
    dividende = taux - math.log(forward / spot) / maturite

    ordonnees = sorted(retenues, key=lambda p: (abs(p.strike - forward), p.strike))
    calibrage, temoins = ordonnees[:STRIKES_CALIBRATION], ordonnees[STRIKES_CALIBRATION:]
    volatilites = [
        _volatilite_implicite(cote.milieu, forward, p.strike, actualisation, maturite, est_call)
        for p in calibrage
        for est_call, cote in ((True, p.call), (False, p.put))
    ]
    volatilite = median(volatilites)
    ecarts_hors_spread = []
    for p in temoins:
        for est_call, cote in ((True, p.call), (False, p.put)):
            prix = _prix_vanille(forward, p.strike, actualisation, volatilite, maturite, est_call)
            ecarts_hors_spread.append(max(cote.bid - prix, prix - cote.ask, 0.0) / spot * 10_000)
    return forward, dividende, volatilite, {
        "paires_retenues": len(retenues),
        "forward_borne_basse": bas,
        "forward_borne_haute": haut,
        "largeur_forward_pb": (haut - bas) / spot * 10_000,
        "strikes_calibration": [p.strike for p in calibrage],
        "volatilite_implicite_min": min(volatilites),
        "volatilite_implicite_max": max(volatilites),
        "temoins_dans_spread": sum(1 for ecart in ecarts_hors_spread if ecart == 0),
        "temoins_total": len(ecarts_hors_spread),
        "mediane_ecart_hors_spread_pb": median(ecarts_hors_spread),
    }


def _sha256(chemin):
    empreinte = hashlib.sha256()
    with chemin.open("rb") as fichier:
        for bloc in iter(lambda: fichier.read(1024 * 1024), b""):
            empreinte.update(bloc)
    return empreinte.hexdigest()


def reconstruire_marche(dossier_csv):
    """Reconstruit uniquement les entrées et diagnostics dérivés des CSV locaux."""
    dossier_csv = Path(dossier_csv)
    fichiers = {nom: dossier_csv / nom for nom in SOURCES}
    paires = _paires_cboe(fichiers["eom_marking_prices_list.csv"])
    parametres_fed = _parametres_fed(fichiers["feds200628.csv"])
    actifs = []
    for symbole, racine in RACINES.items():
        spot, sigma_hist, debut_hist = _clotures(fichiers[f"{symbole}_History.csv"], symbole)
        actif = {
            "symbole": symbole,
            "racine": racine,
            "spot": spot,
            "volatilite_historique": sigma_hist,
            "historique_debut": debut_hist.isoformat(),
            "echeances": [],
        }
        for echeance in ECHEANCES:
            date_iso = echeance.isoformat()
            maturite = annee_act365(DATE_VALORISATION, echeance)
            taux = taux_zero_coupon(parametres_fed, maturite)
            forward, dividende, sigma, diagnostic = _calibrer(
                paires[(racine, date_iso)], spot, taux, maturite,
            )
            fixings = fixings_mensuels(echeance)
            actif["echeances"].append({
                "date": date_iso,
                "maturite": maturite,
                "taux": taux,
                "dividende": dividende,
                "volatilite": sigma,
                "forward": forward,
                "fixings": [jour.isoformat() for jour in fixings],
                "dates_observation": [annee_act365(DATE_VALORISATION, jour) for jour in fixings],
                "diagnostic": diagnostic,
            })
        actifs.append(actif)
    return {
        "date_valorisation": DATE_VALORISATION.isoformat(),
        "horodatage_releve": HEURE_RELEVE.isoformat(),
        "sources": {
            nom: {"url": SOURCES[nom], "sha256": _sha256(chemin)}
            for nom, chemin in fichiers.items()
        },
        "documentation": DOCUMENTATION,
        "conventions": {
            "base_temps": "ACT/365F",
            "spot": "Clôture officielle de l'indice",
            "echeances": "Séries SPXW et RUTW à règlement de clôture PM",
            "fixings": "Clôture du dernier jour ouvré du mois, échéance incluse",
            "taux": "Zéro-coupon continu Treasury, estimation Svensson de la Fed",
            "cotations": "Derniers bid et ask Cboe diffusés",
            "anciennete_max_secondes": ANCIENNETE_MAX_SECONDES,
            "spread_relatif_max": SPREAD_RELATIF_MAX,
            "fenetre_spot": FENETRE_SPOT,
            "fenetre_forward": FENETRE_FORWARD,
            "calibration": "Forward médian projeté dans l'intervalle commun de parité. "
                           "Volatilité médiane des deux jambes aux trois strikes les plus proches.",
            "diagnostic": "Le forward utilise toutes les paires retenues. Les cotations témoins "
                          "sont réservées pour le contrôle de la volatilité.",
            "rendements_historiques": DUREE_HISTORIQUE,
        },
        "actifs": actifs,
    }


def main():
    analyseur = argparse.ArgumentParser(description="Reconstitue l'instantané de marché dérivé.")
    analyseur.add_argument("--csv-dir", required=True, type=Path, help="Dossier des quatre CSV bruts.")
    analyseur.add_argument("--output", default=INSTANTANE, type=Path, help="Fichier JSON de sortie.")
    args = analyseur.parse_args()
    try:
        marche = reconstruire_marche(args.csv_dir)
    except (OSError, ValueError) as erreur:
        analyseur.error(str(erreur))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(marche, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Instantané dérivé écrit dans {args.output}")


if __name__ == "__main__":
    main()
