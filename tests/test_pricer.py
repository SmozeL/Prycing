import math
import unittest

import numpy as np
from scipy.integrate import quad
from scipy.special import ndtr

from asian_pricing.black_scholes import moments_geometriques
from asian_pricing.pricer import pricer_asiatique, pricer_grille


def _reference_deux_fixings(spot, strike, taux, dividende, volatilite, t1, t2, maturite):
    """Intégration indépendante sur le premier fixing normal standard."""
    derive = taux - dividende - volatilite**2 / 2
    ecart = volatilite * math.sqrt(t2 - t1)
    actualisation = math.exp(-taux * maturite) / 2

    def integrande(z, call):
        premier_spot = spot * math.exp(derive * t1 + volatilite * math.sqrt(t1) * z)
        forward = premier_spot * math.exp((taux - dividende) * (t2 - t1))
        strike_residuel = 2 * strike - premier_spot
        if strike_residuel <= 0:
            payoff = forward - strike_residuel if call else 0.0
        else:
            d1 = math.log(forward / strike_residuel) / ecart + ecart / 2
            d2 = d1 - ecart
            if call:
                payoff = forward * ndtr(d1) - strike_residuel * ndtr(d2)
            else:
                payoff = strike_residuel * ndtr(-d2) - forward * ndtr(-d1)
        densite = math.exp(-z**2 / 2) / math.sqrt(2 * math.pi)
        return actualisation * payoff * densite

    return tuple(quad(integrande, -12, 12, args=(call,), epsabs=1e-11)[0] for call in (True, False))


class TestPricer(unittest.TestCase):
    def test_prix_europeen_avec_un_fixing_a_lecheance(self):
        resultat = pricer_grille(
            100, [80, 100, 120], 1, 0.03, 0.01, 0.2, [1],
            methode="controle",
        )
        self.assertEqual(resultat["uniformes_reserves"], 0)
        for contrat in resultat["strikes"]:
            for option in ("call", "put"):
                valeur = contrat[option]
                self.assertAlmostEqual(valeur["controle"]["prix"], valeur["europeenne"], places=11)
                self.assertEqual(valeur["controle"]["erreur_type"], 0.0)

    def test_volatilite_nulle_et_paiement_apres_le_dernier_fixing(self):
        taux, dividende, maturite = 0.04, 0.01, 0.92
        dates = [0.16, 0.35, 0.84]
        moyenne = sum(100 * math.exp((taux - dividende) * t) for t in dates) / len(dates)
        resultat = pricer_grille(100, [99, 104], maturite, taux, dividende, 0, dates)
        self.assertEqual(resultat["uniformes_reserves"], 0)
        for contrat in resultat["strikes"]:
            ecart = moyenne - contrat["strike"]
            for option, montant in (("call", max(ecart, 0)), ("put", max(-ecart, 0))):
                exact = math.exp(-taux * maturite) * montant
                for methode in ("naive", "controle"):
                    estimation = contrat[option][methode]
                    self.assertAlmostEqual(estimation["prix"], exact, places=12)
                    self.assertEqual(estimation["statut"], "exact")

    def test_variance_geometrique_sur_dates_irregulieres(self):
        dates = np.array([0.12, 0.31, 0.87])
        _, variance = moments_geometriques(100, 0.03, 0.01, 0.25, dates)
        covariance = np.minimum(dates[:, None], dates[None, :])
        self.assertAlmostEqual(variance, 0.25**2 * covariance.mean(), places=15)

    def test_quadrature_independante_a_deux_fixings_irreguliers(self):
        args = (100, 102, 0.035, 0.012, 0.24, 0.23, 0.78, 0.91)
        reference = _reference_deux_fixings(*args)
        spot, strike, taux, dividende, vol, t1, t2, maturite = args
        resultat = pricer_grille(
            spot, [strike], maturite, taux, dividende, vol, [t1, t2],
            simulations=120_000, pilote=10_000, graine=2026,
        )["strikes"][0]
        for option, attendu in zip(("call", "put"), reference):
            controle = resultat[option]["controle"]
            naive = resultat[option]["naive"]
            self.assertLess(abs(controle["prix"] - attendu), 4 * controle["erreur_type"])
            self.assertLess(controle["erreur_type"], naive["erreur_type"])
        self.assertLessEqual(
            resultat["call"]["geometrique"], resultat["call"]["controle"]["ic"][1],
        )
        self.assertGreaterEqual(
            resultat["put"]["geometrique"], resultat["put"]["controle"]["ic"][0],
        )

    def test_reproductibilite_et_sous_flux_box_muller(self):
        args = (100, [95, 100, 105], 1.0, 0.04, 0.02, 0.25, [0.17, 0.40, 0.91])
        reglages = dict(simulations=4097, pilote=17, graine=144, decalage=103)
        tous = pricer_grille(*args, **reglages)
        self.assertEqual(tous, pricer_grille(*args, **reglages))
        controle = pricer_grille(*args, **reglages, methode="controle")
        self.assertEqual(tous["uniformes_reserves"], 52 + 12_292)
        naive = pricer_grille(*args, **{**reglages, "decalage": 103 + 52}, methode="naive")
        for i in range(len(args[1])):
            for option in ("call", "put"):
                self.assertEqual(tous["strikes"][i][option]["naive"], naive["strikes"][i][option]["naive"])
                self.assertEqual(tous["strikes"][i][option]["controle"], controle["strikes"][i][option]["controle"])

    def test_payoffs_rares_et_frequence(self):
        resultat = pricer_asiatique(100, 400, 0.15, 0.03, 0.5, frequence=12)
        self.assertEqual(len(resultat["dates_observation"]), 6)
        self.assertEqual(resultat["dates_observation"][-1], 0.5)
        for methode in ("naive", "controle"):
            estimation = resultat["call"][methode]
            self.assertEqual(estimation["statut"], "payoffs_rares")
            self.assertIsNone(estimation["ic"])
            self.assertEqual(estimation["payoffs_positifs"], 0)
        with self.assertRaises(ValueError):
            pricer_grille(100, [100], 1, 0.03, 0.01, 0.2, [0.5, 0.4])
