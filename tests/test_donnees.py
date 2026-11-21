import unittest
from datetime import date

from asian_pricing.donnees import charger_marche


class TestDonnees(unittest.TestCase):
    def test_instantane_alphabet_et_calendrier(self):
        marche = charger_marche()
        actif, = marche["actifs"]
        self.assertEqual(actif["symbole"], "GOOGL")
        self.assertEqual(actif["spot"], 313.0)
        self.assertEqual(marche["strike_ratios"], [0.9, 1.0, 1.1])
        self.assertEqual([len(e["fixings"]) for e in actif["echeances"]], [6, 12, 24])

        origine = date.fromisoformat(marche["date_valorisation"])
        for echeance in actif["echeances"]:
            with self.subTest(echeance=echeance["date"]):
                fixings = echeance["fixings"]
                dates = [(date.fromisoformat(f) - origine).days / 365 for f in fixings]
                self.assertEqual(fixings, sorted(set(fixings)))
                self.assertEqual(fixings[-1], echeance["date"])
                self.assertGreater(dates[0], 0)
                self.assertEqual(echeance["dates_observation"], dates)
                self.assertEqual(echeance["maturite"], dates[-1])
                self.assertAlmostEqual(echeance["dividende"], 0.83 / actif["spot"])


if __name__ == "__main__":
    unittest.main()
