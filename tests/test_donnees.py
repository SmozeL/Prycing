import math
import unittest
from datetime import date

from asian_pricing.donnees import (
    ECHEANCES, Fourchette, Paire, _calibrer, _prix_vanille, charger_marche,
)


class TestDonnees(unittest.TestCase):
    def test_calibrage_sur_fourchettes_synthetiques(self):
        spot, taux, dividende, volatilite, maturite = 100, 0.04, 0.02, 0.24, 0.5
        forward = spot * math.exp((taux - dividende) * maturite)
        actualisation = math.exp(-taux * maturite)
        paires = []
        for strike in (100, 100.5, 101, 101.5, 102):
            call, put = (
                _prix_vanille(forward, strike, actualisation, volatilite, maturite, est_call)
                for est_call in (True, False)
            )
            paires.append(Paire(strike, Fourchette(call - 0.01, call + 0.01),
                                Fourchette(put - 0.01, put + 0.01)))

        f, q, sigma, diagnostic = _calibrer(paires, spot, taux, maturite)
        self.assertAlmostEqual(f, forward, places=12)
        self.assertAlmostEqual(q, dividende, places=12)
        self.assertAlmostEqual(sigma, volatilite, places=10)
        self.assertEqual(diagnostic["temoins_dans_spread"], 4)
        self.assertEqual(diagnostic["temoins_total"], 4)

    def test_calendrier_et_parite_de_linstantane(self):
        marche = charger_marche()
        origine = date.fromisoformat(marche["date_valorisation"])
        self.assertEqual([a["symbole"] for a in marche["actifs"]], ["SPX", "RUT"])
        for actif in marche["actifs"]:
            self.assertEqual([e["date"] for e in actif["echeances"]],
                             [d.isoformat() for d in ECHEANCES])
            for echeance in actif["echeances"]:
                with self.subTest(indice=actif["symbole"], echeance=echeance["date"]):
                    fixings = echeance["fixings"]
                    self.assertEqual(fixings[-1], echeance["date"])
                    self.assertEqual(fixings, sorted(set(fixings)))
                    self.assertEqual(echeance["dates_observation"], [
                        (date.fromisoformat(d) - origine).days / 365 for d in fixings
                    ])
                    self.assertAlmostEqual(echeance["forward"], actif["spot"] * math.exp(
                        (echeance["taux"] - echeance["dividende"]) * echeance["maturite"]
                    ))
                    if echeance["date"] == "2027-06-30":
                        self.assertIn("2027-05-28", fixings)


if __name__ == "__main__":
    unittest.main()
