"""Lance le sujet 2 en un clic dans VS Code, ou avec python run_tp.py."""

import argparse
from pathlib import Path

from asian_pricing.donnees import charger_marche
from asian_pricing.experiences import analyser_marche, exporter_resultats

_REPERTOIRE = Path(__file__).resolve().parent


def afficher(resultats):
    print("\nPrimes à la monnaie en points d'indice")
    print(f"{'Indice':<7} {'Échéance':<11} {'Type':<5} {'Naïf':>10} "
          f"{'Contrôlé':>10} {'Européen':>10} {'Écart (pb)':>11}")
    for ligne in resultats["prix"]:
        if ligne["moneyness"] == 1.0:
            print(f"{ligne['indice']:<7} {ligne['echeance']:<11} {ligne['type']:<5} "
                  f"{ligne['naif']:10.3f} {ligne['controle']:10.3f} "
                  f"{ligne['europeenne']:10.3f} {ligne['ecart_pb_spot']:+11.2f}")

    print("\nPrécision cible à la monnaie · demi-IC à 95 % de 1 pb du spot")
    print(f"{'Indice':<7} {'Méthode':<11} {'Trajectoires':>12} "
          f"{'Pilote':>8} {'Temps (ms)':>11} {'Demi-IC max':>12} {'Cible':>8}")
    for ligne in resultats["performance"]:
        methode = "Naïf" if ligne["methode"] == "naive" else "Contrôlé"
        demi_ic = ligne["demi_ic95_max_pb"]
        largeur = "n.d." if demi_ic is None else f"{demi_ic:.3f} pb"
        statut = "atteinte" if ligne["cible_atteinte"] else "manquée"
        print(f"{ligne['indice']:<7} {methode:<11} {ligne['simulations']:>12,} "
              f"{ligne['pilote']:>8,} {ligne['temps_ms']:>11.2f} "
              f"{largeur:>12} {statut:>8}")
    print("Temps médian et demi-IC maximal sur les répétitions, pilote compris.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--donnees", type=Path, default=_REPERTOIRE / "data" / "market_snapshot.json")
    parser.add_argument("--sortie", type=Path, default=_REPERTOIRE / "resultats")
    parser.add_argument("--simulations", type=int, default=50_000)
    parser.add_argument("--pilote", type=int, default=5_000)
    parser.add_argument("--graine", type=int, default=42)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--plafond", type=int, default=2_000_000)
    args = parser.parse_args()

    try:
        marche = charger_marche(args.donnees)
        indices = ", ".join(actif["symbole"] for actif in marche["actifs"])
        print(f"Étude du {marche['date_valorisation']} · {indices}", flush=True)
        resultats = analyser_marche(
            marche, simulations=args.simulations, pilote=args.pilote,
            graine=args.graine, repetitions=args.repetitions, plafond=args.plafond,
        )
        exporter_resultats(resultats, args.sortie)
    except (ValueError, OSError) as erreur:
        parser.error(str(erreur))

    afficher(resultats)
    print(f"Grille complète et mesures enregistrées dans {args.sortie.resolve()}")


if __name__ == "__main__":
    main()
