"""Chargement de l’instantané de marché utilisé par les expériences."""

import json
from pathlib import Path


_INSTANTANE = Path(__file__).resolve().parents[1] / "data" / "googl_snapshot.json"


def charger_marche():
    """Lit les paramètres, le calendrier et les sources sans accès réseau."""
    with _INSTANTANE.open(encoding="utf-8") as fichier:
        return json.load(fichier)
