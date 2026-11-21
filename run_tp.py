"""Exécute les comparaisons de l’énoncé 2 sur Alphabet (GOOGL)."""

import argparse
from pathlib import Path
from secrets import randbelow

from asian_pricing.donnees import charger_marche
from asian_pricing.experiences import analyser_marche, exporter_resultats
from asian_pricing.rng import PERIODE


_SORTIE = Path(__file__).resolve().parent / "resultats"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sortie", type=Path, default=_SORTIE, help="Dossier des deux CSV.")
    parser.add_argument("--graine", type=int, help="Graine à rejouer (tirée par défaut).")
    args = parser.parse_args()
    graine = randbelow(PERIODE) + 1 if args.graine is None else args.graine

    try:
        marche = charger_marche()
        actif, = marche["actifs"]
        print(f"{actif['symbole']} · Relevé du {marche['date_valorisation']} · Graine {graine}", flush=True)
        resultats = analyser_marche(marche, graine=graine)
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
