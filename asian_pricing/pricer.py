"""Monte-Carlo des options asiatiques arithmétiques sous Black–Scholes."""

import math
from numbers import Integral
from statistics import NormalDist

import numpy as np

from .black_scholes import moments_geometriques, prix_europeen, prix_lognormal
from .contrats import dates_regulieres, valider_contrat
from .rng import PERIODE, flux_uniformes, normales, uniformes_necessaires

_TAILLE_BLOC = 4096  # Taille paire pour réserver exactement les tirages par phase.
_MIN_PAYOFFS_POSITIFS = 20
_OPTIONS = ("call", "put")


def _simuler_moyennes(flux, nombre, spot, pas, taux, dividende, volatilite, avec_geometrique):
    """Simule les moyennes A et G une fois pour tous les strikes."""
    arithmetiques = np.empty(nombre)
    geometriques = np.empty(nombre) if avec_geometrique else None
    derive = (taux - dividende - volatilite**2 / 2) * pas
    diffusion = volatilite * np.sqrt(pas)
    log_spot = math.log(spot)
    with np.errstate(over="raise", invalid="raise"):
        for debut in range(0, nombre, _TAILLE_BLOC):
            fin = min(debut + _TAILLE_BLOC, nombre)
            log_cours = normales(flux, (fin - debut) * pas.size).reshape(fin - debut, pas.size)
            log_cours *= diffusion
            log_cours += derive
            np.cumsum(log_cours, axis=1, out=log_cours)
            log_cours += log_spot
            if avec_geometrique:
                geometriques[debut:fin] = np.exp(log_cours.mean(axis=1))
            arithmetiques[debut:fin] = np.exp(log_cours, out=log_cours).mean(axis=1)
    return arithmetiques, geometriques


def _payoffs(moyennes, strike, actualisation):
    """Renvoie les colonnes call et put, actualisées à la date de valorisation."""
    ecarts = moyennes - strike
    return actualisation * np.column_stack((np.maximum(ecarts, 0), np.maximum(-ecarts, 0)))


def _centrer(payoffs):
    # Évite les carrés de valeurs minuscules ou très grandes dans les statistiques.
    echelle = float(np.max(payoffs))
    if echelle == 0.0 or np.ptp(payoffs) == 0.0:
        return None, echelle
    normes = payoffs / echelle
    return normes - normes.mean(), echelle


def _coefficient_controle(arithmetique, geometrique):
    a, echelle_a = _centrer(arithmetique)
    g, echelle_g = _centrer(geometrique)
    if a is None or g is None:
        return 0.0
    variance_g = float(np.dot(g, g))
    if variance_g == 0.0:
        return 0.0
    beta = float(np.dot(a, g)) / variance_g * (echelle_a / echelle_g)
    return beta if math.isfinite(beta) else 0.0


def _correlation(arithmetique, geometrique):
    a, _ = _centrer(arithmetique)
    g, _ = _centrer(geometrique)
    if a is None or g is None:
        return None
    norme = math.sqrt(float(np.dot(a, a))) * math.sqrt(float(np.dot(g, g)))
    if norme == 0.0:
        return None
    return float(np.clip(np.dot(a, g) / norme, -1.0, 1.0))


def _estimation(payoffs, observations_utiles, quantile):
    echelle = max(abs(float(payoffs.min())), abs(float(payoffs.max())))
    if echelle == 0.0:
        prix = erreur = 0.0
    else:
        normes = payoffs / echelle
        prix = float(normes.mean()) * echelle
        erreur = float(normes.std(ddof=1)) / math.sqrt(normes.size) * echelle
    statut = "ok"
    if observations_utiles < _MIN_PAYOFFS_POSITIFS:
        statut = "payoffs_rares"
    elif prix < 0.0 or erreur == 0.0:
        statut = "estimation_peu_informative"
    demi_largeur = quantile * erreur
    return {
        "prix": prix,
        "erreur_type": erreur,
        "ic": (prix - demi_largeur, prix + demi_largeur) if statut == "ok" else None,
        "payoffs_positifs": int(observations_utiles),
        "statut": statut,
    }


def _prix_exact(prix):
    return {"prix": prix, "erreur_type": 0.0, "ic": (prix, prix), "statut": "exact"}


def pricer_grille(
    spot: float,
    strikes,
    maturite: float,
    taux: float,
    dividende: float,
    volatilite: float,
    dates_observation,
    *,
    simulations: int = 50_000,
    pilote: int = 5_000,
    graine: int = 42,
    decalage: int = 0,
    methode: str = "les_deux",
    niveau_confiance: float = 0.95,
) -> dict:
    """Valorise une grille de strikes avec les mêmes moyennes par trajectoire.

    Les dates d'observation, positives et croissantes, sont des fractions
    d'année depuis la valorisation. Toutes les options sont payées à T.
    Les taux et la volatilité annualisée sont fournis en décimal.

    Le lot pilote estime les coefficients du contrôle géométrique. Les
    estimations naïve et contrôlée du mode « les_deux » partagent ensuite
    un lot de production distinct. Le résultat indique le nombre exact
    d'uniformes utilisés pour démarrer le prochain sous-flux disjoint.
    """
    strikes, dates = valider_contrat(
        spot, strikes, maturite, taux, dividende, volatilite, dates_observation,
    )
    if methode not in ("naive", "controle", "les_deux"):
        raise ValueError("La méthode doit être « naive », « controle » ou « les_deux ».")
    if not isinstance(simulations, Integral) or simulations < 2:
        raise ValueError("Le nombre de trajectoires doit être un entier supérieur ou égal à 2.")
    if not 0.0 < niveau_confiance < 1.0:
        raise ValueError("Le niveau de confiance doit appartenir à ]0,1[.")
    avec_naif = methode != "controle"
    avec_controle = methode != "naive"
    deterministe = volatilite == 0.0
    calibrer = avec_controle and not deterministe and dates.size > 1
    simuler = not deterministe and (avec_naif or calibrer)
    if calibrer and (not isinstance(pilote, Integral) or pilote < 2):
        raise ValueError("Le contrôle requiert au moins deux trajectoires pilotes.")

    flux = flux_uniformes(graine, decalage)
    reserves = uniformes_necessaires(int(pilote) * dates.size) if calibrer else 0
    if simuler:
        reserves += uniformes_necessaires(int(simulations) * dates.size)
    if int(decalage) + reserves > PERIODE:
        raise ValueError("Le sous-flux demandé dépasse la période du générateur.")

    log_actualisation = -taux * maturite
    actualisation = math.exp(log_actualisation)
    quantile = -NormalDist().inv_cdf((1.0 - niveau_confiance) / 2)
    moyenne_log, variance_log = moments_geometriques(spot, taux, dividende, volatilite, dates)
    pas = np.diff(dates, prepend=0.0)
    a_pilote = g_pilote = a_prod = g_prod = None
    if calibrer:
        a_pilote, g_pilote = _simuler_moyennes(
            flux, int(pilote), spot, pas, taux, dividende, volatilite, True,
        )
    if simuler:
        a_prod, g_prod = _simuler_moyennes(
            flux, int(simulations), spot, pas, taux, dividende, volatilite, calibrer,
        )
    if deterministe:
        moyenne_deterministe = float(np.exp(math.log(spot) + (taux - dividende) * dates).mean())

    resultats = []
    for strike in strikes:
        strike = float(strike)
        europeens = prix_europeen(spot, strike, maturite, taux, dividende, volatilite)
        geometriques = prix_lognormal(moyenne_log, variance_log, strike, log_actualisation)
        resultats_strike = {"strike": strike}
        if simuler:
            x = _payoffs(a_prod, strike, actualisation)
        if calibrer:
            y = _payoffs(g_prod, strike, actualisation)
            x_pilote = _payoffs(a_pilote, strike, actualisation)
            y_pilote = _payoffs(g_pilote, strike, actualisation)
        if deterministe:
            exacts = _payoffs(np.array([moyenne_deterministe]), strike, actualisation)[0]

        for i, option in enumerate(_OPTIONS):
            resultat = {"europeenne": europeens[i], "geometrique": geometriques[i]}
            if deterministe:
                if avec_naif:
                    resultat["naive"] = _prix_exact(float(exacts[i]))
                if avec_controle:
                    resultat["controle"] = dict(_prix_exact(float(exacts[i])), beta=0.0, correlation=None)
            else:
                if simuler:
                    payoffs = x[:, i]
                    positifs = np.count_nonzero(payoffs > 0)
                if avec_naif:
                    resultat["naive"] = _estimation(payoffs, positifs, quantile)
                if calibrer:
                    beta = _coefficient_controle(x_pilote[:, i], y_pilote[:, i])
                    corriges = payoffs - beta * (y[:, i] - geometriques[i])
                    resultat["controle"] = dict(
                        _estimation(corriges, positifs, quantile),
                        beta=beta,
                        correlation=_correlation(payoffs, y[:, i]),
                    )
                elif avec_controle:
                    # Avec un seul fixing A = G, le contrôle rend le prix exact.
                    resultat["controle"] = dict(_prix_exact(geometriques[i]), beta=1.0, correlation=1.0)
            resultats_strike[option] = resultat
        resultats.append(resultats_strike)
    return {
        "strikes": resultats,
        "dates_observation": dates.tolist(),
        "simulations": int(simulations) if simuler else 0,
        "pilote": int(pilote) if calibrer else 0,
        "niveau_confiance": niveau_confiance,
        "uniformes_reserves": reserves,
    }


def pricer_asiatique(
    spot: float,
    strike: float,
    volatilite: float,
    taux: float,
    maturite: float,
    dividende: float = 0.0,
    *,
    frequence: float = 12,
    dates_observation=None,
    **reglages,
) -> dict:
    """Valorise un strike selon une fréquence annuelle ou des dates explicites."""
    dates = dates_regulieres(maturite, frequence) if dates_observation is None else dates_observation
    resultat = pricer_grille(
        spot, [strike], maturite, taux, dividende, volatilite, dates, **reglages,
    )
    contrat = resultat.pop("strikes")[0]
    return {**resultat, **contrat}
