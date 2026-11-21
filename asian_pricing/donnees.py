"""Chargement de l’instantané de marché utilisé par les expériences."""

import json
from pathlib import Path


INSTANTANE = Path(__file__).resolve().parents[1] / "data" / "googl_snapshot.json"


def charger_marche(chemin=None):
    """Lit les paramètres, le calendrier et les sources sans accès réseau."""
    chemin = INSTANTANE if chemin is None else Path(chemin)
    with chemin.open(encoding="utf-8") as fichier:
        return json.load(fichier)


if __name__ == "__main__":
    # L’ancienne commande de calibration d’indices reste accessible.
    from .calibrage_indices import main

    main()
