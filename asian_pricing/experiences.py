"""Grille du TP, sensibilité et chronométrage du Monte-Carlo."""

import csv
import math
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter

from .pricer import pricer_grille

_TYPES = ("call", "put")
_METHODES = ("naive", "controle")
_STRIKES_RELATIFS = (0.90, 1.00, 1.10)
_CIBLE_PB = 1.0
_MARGE_DIMENSIONNEMENT = 1.10
_MIN_PRODUCTION = 512


class _Simulations:
    """Réserve des plages consécutives et permet un appariement explicite."""

    def __init__(self, graine, pilote):
        self.graine = graine
        self.pilote = pilote
        self.prochain = 0

    def __call__(
        self, actif, echeance, strikes, simulations, methode, *,
        volatilite=None, decalage_partage=None,
    ):
        depart = self.prochain if decalage_partage is None else decalage_partage
        resultat = pricer_grille(
            actif["spot"],
            strikes,
            echeance["maturite"],
            echeance["taux"],
            echeance["dividende"],
            echeance["volatilite"] if volatilite is None else volatilite,
            echeance["dates_observation"],
            simulations=simulations,
            pilote=self.pilote,
            graine=self.graine,
            decalage=depart,
            methode=methode,
            niveau_confiance=0.95,
        )
        if decalage_partage is None:
            self.prochain += resultat["uniformes_reserves"]
        return resultat["strikes"]


def _bornes(estimation):
    return estimation["ic"] if estimation["ic"] is not None else (None, None)


def _demi_ic_pb(estimation, spot):
    bas, haut = _bornes(estimation)
    return None if bas is None else (haut - bas) * 5_000 / spot


def _prix(marche, actif, echeance, estimations, simulations, pilote, graine, decalage):
    lignes = []
    spot = actif["spot"]
    for contrat in estimations:
        for type_option in _TYPES:
            option = contrat[type_option]
            naif = option["naive"]
            controle = option["controle"]
            bas_naif, haut_naif = _bornes(naif)
            bas_controle, haut_controle = _bornes(controle)
            se_naif, se_controle = naif["erreur_type"], controle["erreur_type"]
            gain = None
            if bas_naif is not None and bas_controle is not None and se_controle > 0:
                gain = se_naif / se_controle
            ecart = controle["prix"] - option["europeenne"]
            lignes.append({
                "indice": actif["symbole"],
                "racine": actif["racine"],
                "date_valorisation": marche["date_valorisation"],
                "echeance": echeance["date"],
                "maturite": echeance["maturite"],
                "observations": len(echeance["dates_observation"]),
                "spot": spot,
                "strike": contrat["strike"],
                "moneyness": contrat["strike"] / spot,
                "type": type_option,
                "taux": echeance["taux"],
                "dividende": echeance["dividende"],
                "volatilite": echeance["volatilite"],
                "simulations": simulations,
                "pilote": pilote,
                "graine": graine,
                "decalage": decalage,
                "naif": naif["prix"],
                "controle": controle["prix"],
                "europeenne": option["europeenne"],
                "geometrique": option["geometrique"],
                "se_naif": se_naif,
                "se_controle": se_controle,
                "ic95_inf_naif": bas_naif,
                "ic95_sup_naif": haut_naif,
                "ic95_inf_controle": bas_controle,
                "ic95_sup_controle": haut_controle,
                "beta": controle.get("beta"),
                "correlation": controle.get("correlation"),
                "gain_precision": gain,
                "ecart_points": ecart,
                "ecart_pb_spot": 10_000 * ecart / spot,
            })
    return lignes


def _sensibilite(calculer, actif, echeance, implicite, simulations, decalage):
    spot = actif["spot"]
    historique, = calculer(
        actif, echeance, [spot], simulations, "les_deux",
        volatilite=actif["volatilite_historique"], decalage_partage=decalage,
    )
    lignes = []
    for type_option in _TYPES:
        prix_imp = implicite[type_option]["controle"]
        prix_hist = historique[type_option]["controle"]
        lignes.append({
            "indice": actif["symbole"],
            "echeance": echeance["date"],
            "type": type_option,
            "spot": spot,
            "strike": spot,
            "decalage": decalage,
            "volatilite_implicite": echeance["volatilite"],
            "volatilite_historique": actif["volatilite_historique"],
            "prix_implicite": prix_imp["prix"],
            "prix_historique": prix_hist["prix"],
            "demi_ic95_implicite_pb": _demi_ic_pb(prix_imp, spot),
            "demi_ic95_historique_pb": _demi_ic_pb(prix_hist, spot),
            "ecart_historique_implicite_pb": 10_000 * (prix_hist["prix"] - prix_imp["prix"]) / spot,
        })
    return lignes


def _tailles_cibles(echantillon, spot, dimensionnement, plafond):
    """Dimensionne la production avant chronométrage avec une marge de 10 %."""
    tailles = {}
    for methode in _METHODES:
        demi_largeurs = [_demi_ic_pb(echantillon[t][methode], spot) for t in _TYPES]
        if any(largeur is None for largeur in demi_largeurs):
            tailles[methode] = (plafond, True)
            continue
        facteur = max(demi_largeurs) / _CIBLE_PB
        n_demande = max(
            _MIN_PRODUCTION,
            math.ceil(_MARGE_DIMENSIONNEMENT * dimensionnement * facteur**2),
        )
        tailles[methode] = (min(n_demande, plafond), n_demande > plafond)
    return tailles


def _chronometrer(calculer, actif, echeance, tailles, repetitions):
    """Alterne l'ordre des méthodes et mesure le pricer sur de nouveaux sous-flux."""
    spot = actif["spot"]
    temps = {methode: [] for methode in _METHODES}
    largeurs = {methode: {t: [] for t in _TYPES} for methode in _METHODES}
    for i in range(repetitions):
        ordre = _METHODES if i % 2 == 0 else _METHODES[::-1]
        for methode in ordre:
            debut = perf_counter()
            contrat, = calculer(actif, echeance, [spot], tailles[methode], methode)
            temps[methode].append((perf_counter() - debut) * 1_000)
            for t in _TYPES:
                largeurs[methode][t].append(_demi_ic_pb(contrat[t][methode], spot))

    lignes = []
    for methode in _METHODES:
        # Un IC manquant rend la précision non établie pour ce type.
        maxima = {
            t: None if any(v is None for v in valeurs) else max(valeurs)
            for t, valeurs in largeurs[methode].items()
        }
        pire = None if any(v is None for v in maxima.values()) else max(maxima.values())
        lignes.append({
            "indice": actif["symbole"],
            "echeance": echeance["date"],
            "methode": methode,
            "simulations": tailles[methode],
            "pilote": calculer.pilote if methode == "controle" else 0,
            "repetitions": repetitions,
            "temps_ms": median(temps[methode]),
            "demi_ic95_call_pb": maxima["call"],
            "demi_ic95_put_pb": maxima["put"],
            "demi_ic95_max_pb": pire,
        })
    return lignes


def analyser_marche(
    marche, *, simulations=50_000, pilote=5_000, graine=42, repetitions=5,
    dimensionnement=30_000, plafond=2_000_000,
):
    """Construit la grille du TP et mesure la précision au strike égal au spot."""
    if min(simulations, pilote, dimensionnement, plafond) < 2 or repetitions < 1:
        raise ValueError("Il faut au moins deux trajectoires et une répétition.")

    calculer = _Simulations(graine, pilote)
    resultats = {nom: [] for nom in ("prix", "performance", "convergence", "sensibilite")}
    for actif in marche["actifs"]:
        echeances = sorted(actif["echeances"], key=lambda e: e["date"])
        centrale = echeances[len(echeances) // 2]
        strikes = [actif["spot"] * ratio for ratio in _STRIKES_RELATIFS]
        for echeance in echeances:
            decalage = calculer.prochain
            estimations = calculer(actif, echeance, strikes, simulations, "les_deux")
            resultats["prix"].extend(
                _prix(marche, actif, echeance, estimations, simulations, pilote, graine, decalage)
            )
            if echeance is centrale:
                resultats["sensibilite"].extend(
                    _sensibilite(calculer, actif, echeance, estimations[1], simulations, decalage)
                )

        # La grille a déjà échauffé le pricer. Le dimensionnement ne fait pas
        # partie du chronométrage. Le pilote de chaque production contrôlée si.
        echantillon, = calculer(actif, centrale, [actif["spot"]], dimensionnement, "les_deux")
        tailles = _tailles_cibles(echantillon, actif["spot"], dimensionnement, plafond)
        mesures = _chronometrer(
            calculer, actif, centrale, {m: v[0] for m, v in tailles.items()}, repetitions,
        )
        for mesure in mesures:
            demi_largeur = mesure["demi_ic95_max_pb"]
            resultats["performance"].append({
                **mesure,
                "cible_pb": _CIBLE_PB,
                "dimensionnement": dimensionnement,
                "cible_atteinte": demi_largeur is not None and demi_largeur <= _CIBLE_PB,
                "plafond_atteint": tailles[mesure["methode"]][1],
            })

        for n in sorted({min(simulations, taille) for taille in (2_000, 10_000, 50_000)}):
            resultats["convergence"].extend(
                _chronometrer(calculer, actif, centrale, dict.fromkeys(_METHODES, n), repetitions)
            )
    return resultats


def exporter_resultats(resultats, dossier):
    """Écrit les CSV du TP à partir des résultats en mémoire."""
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
