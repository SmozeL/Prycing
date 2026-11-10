"""Compose le rapport de deux pages à partir des CSV du script d'étude."""

import argparse
import csv
import json
import math
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

W, H = A4
MARGE = 44
LARGEUR = W - 2 * MARGE
ENCRE = colors.HexColor("#142638")
TEXTE = colors.HexColor("#374C60")
GRIS = colors.HexColor("#D5E1EB")
FOND = colors.HexColor("#F1F6FA")
BLEU = colors.HexColor("#125882")
SARCELLE = colors.HexColor("#006D66")
ORANGE = colors.HexColor("#A84E21")
BLANC = colors.white
DATES = {"2027-01-29": "29 jan.", "2027-03-31": "31 mars", "2027-06-30": "30 juin"}
INDICES = ("SPX", "RUT")
METHODES = {"naive": ("Naïf", ORANGE), "controle": ("Contrôle", SARCELLE)}


def fr(valeur, decimales=0):
    return f"{float(valeur):,.{decimales}f}".replace(",", "\u00a0").replace(".", ",")


def lire_csv(dossier, nom):
    with (dossier / nom).open(encoding="utf-8", newline="") as fichier:
        return list(csv.DictReader(fichier))


def texte(pdf, x, y, valeur, *, taille=10, police="Helvetica", couleur=ENCRE):
    pdf.setFillColor(couleur)
    pdf.setFont(police, taille)
    pdf.drawString(x, y, valeur)


def centre(pdf, x, y, valeur, *, taille=9, couleur=ENCRE, gras=False):
    pdf.setFillColor(couleur)
    pdf.setFont("Helvetica-Bold" if gras else "Helvetica", taille)
    pdf.drawCentredString(x, y, valeur)


def paragraphe(pdf, html, y, *, taille=10, leading=14, couleur=TEXTE):
    style = ParagraphStyle(
        "rapport", fontName="Helvetica", fontSize=taille,
        leading=leading, textColor=couleur,
    )
    p = Paragraph(html, style)
    _, hauteur = p.wrap(LARGEUR, H)
    p.drawOn(pdf, MARGE, y - hauteur)
    return y - hauteur


def rectangle(pdf, x, y, largeur, hauteur, couleur):
    pdf.setFillColor(couleur)
    pdf.rect(x, y, largeur, hauteur, stroke=0, fill=1)


def trait(pdf, x, y, x2, y2, couleur=GRIS):
    pdf.setStrokeColor(couleur)
    pdf.setLineWidth(0.65)
    pdf.line(x, y, x2, y2)


def entete(pdf, numero, titre, sous_titre):
    rectangle(pdf, MARGE, H - 47, 23, 3, SARCELLE)
    texte(pdf, MARGE + 32, H - 48, "PRYCING  /  PROJET ING 4  /  SUJET 2",
          taille=9, police="Helvetica-Bold", couleur=SARCELLE)
    texte(pdf, MARGE, H - 93, titre, taille=32, police="Times-Roman")
    texte(pdf, MARGE, H - 112, sous_titre, taille=10, couleur=TEXTE)
    trait(pdf, MARGE, 46, W - MARGE, 46)
    texte(pdf, MARGE, 30, "Relevé de marché du 30 octobre 2026", taille=8, couleur=TEXTE)
    centre(pdf, W - MARGE - 10, 30, f"{numero} / 2", taille=8, gras=True)


def section(pdf, y, nombre, titre):
    texte(pdf, MARGE, y, nombre, taille=10, police="Helvetica-Bold", couleur=SARCELLE)
    texte(pdf, MARGE + 26, y - 1, titre, taille=13, police="Helvetica-Bold")
    return y - 13


def tableau(pdf, y, en_tetes, lignes, fractions, *, hauteur=18):
    largeurs = [LARGEUR * fraction for fraction in fractions]
    rectangle(pdf, MARGE, y - hauteur, LARGEUR, hauteur, ENCRE)
    x = MARGE
    for titre, largeur in zip(en_tetes, largeurs):
        centre(pdf, x + largeur / 2, y - hauteur / 2 - 3, titre,
               couleur=BLANC, gras=True, taille=8.1)
        x += largeur
    y -= hauteur
    for i, ligne in enumerate(lignes):
        if i % 2 == 0:
            rectangle(pdf, MARGE, y - hauteur, LARGEUR, hauteur, FOND)
        x = MARGE
        for j, (valeur, largeur) in enumerate(zip(ligne, largeurs)):
            centre(pdf, x + largeur / 2, y - hauteur / 2 - 3, str(valeur),
                   taille=8.8, gras=(j == 0))
            x += largeur
        y -= hauteur
    trait(pdf, MARGE, y, W - MARGE, y)
    return y


def carte(pdf, x, haut, largeur, indice, option, donnees, borne):
    dates = sorted({ligne["echeance"] for ligne in donnees})
    texte(pdf, x, haut, f"{indice}  /  {option.capitalize()}",
          taille=11, police="Helvetica-Bold")
    marge = 46
    cellule = (largeur - marge) / 3
    for i, label in enumerate(("90 %", "100 %", "110 %")):
        centre(pdf, x + marge + (i + 0.5) * cellule, haut - 16, label,
               couleur=TEXTE, taille=8)
    for j, date in enumerate(dates):
        y = haut - 36 - 19 * j
        texte(pdf, x, y + 5, DATES.get(date, date), taille=8.1, couleur=TEXTE)
        for i, ratio in enumerate((0.9, 1.0, 1.1)):
            valeur = next(
                float(ligne["ecart_pb_spot"]) for ligne in donnees
                if ligne["echeance"] == date and math.isclose(float(ligne["moneyness"]), ratio)
            )
            poids = min(abs(valeur) / borne, 1)
            couleur = colors.linearlyInterpolatedColor(
                FOND, BLEU if valeur < 0 else ORANGE, 0, 1, poids,
            )
            x_cellule = x + marge + i * cellule
            rectangle(pdf, x_cellule, y, cellule - 2, 17, couleur)
            signe = "+" if valeur > 0 else ""
            centre(pdf, x_cellule + (cellule - 2) / 2, y + 5,
                   signe + fr(valeur, 1), couleur=BLANC if poids >= 0.62 else ENCRE,
                   gras=True, taille=8.3)


def page_prix(pdf, prix, marche):
    entete(pdf, 1, "Valoriser la moyenne", "Calls et puts asiatiques arithmétiques sur SPX et RUT")
    y = H - 139
    rectangle(pdf, MARGE, y - 45, LARGEUR, 45, FOND)
    for i, actif in enumerate(marche["actifs"]):
        x = MARGE + 13 + i * 174
        texte(pdf, x, y - 14, actif["symbole"] + " · clôture", taille=8, couleur=SARCELLE,
              police="Helvetica-Bold")
        texte(pdf, x, y - 33, fr(actif["spot"], 2) + " points", taille=14)
    texte(pdf, MARGE + 361, y - 14, "CALENDRIER", taille=8, couleur=SARCELLE,
          police="Helvetica-Bold")
    texte(pdf, MARGE + 361, y - 33, "Fixings mensuels", taille=13)
    y = paragraphe(
        pdf, "Les deux indices partagent la devise USD et offrent des échéances PM communes. "
        "Le forward est estimé par parité call-put et la volatilité implicite près du forward. "
        "Le taux continu vient de la courbe Treasury estimée par la Fed. Les asiatiques "
        "sont définies pour cette étude.", y - 55,
    )
    y = section(pdf, y - 23, "01", "Écart entre l'asiatique et l'européenne")
    y = paragraphe(
        pdf, "Prix asiatique avec contrôle moins prix européen, en points de base du spot. "
        "Les colonnes indiquent K/S<sub>0</sub>. La même échelle s'applique aux quatre cartes.",
        y, taille=9.2, leading=12,
    )
    borne = max(1, max(abs(float(ligne["ecart_pb_spot"])) for ligne in prix))
    ecart = 22
    largeur = (LARGEUR - ecart) / 2
    haut = y - 19
    for j, indice in enumerate(INDICES):
        for i, option in enumerate(("call", "put")):
            selection = [l for l in prix if l["indice"] == indice and l["type"] == option]
            carte(pdf, MARGE + i * (largeur + ecart), haut - j * 96, largeur,
                  indice, option, selection, borne)
    y = haut - 176
    texte(pdf, MARGE, y, f"Échelle commune  -{fr(borne, 1)} à +{fr(borne, 1)} pb",
          taille=8.5, couleur=TEXTE)
    y = section(pdf, y - 24, "02", "Primes à la monnaie en points d'indice")
    lignes = []
    for indice in INDICES:
        dates = sorted({p["echeance"] for p in prix if p["indice"] == indice})
        for date in dates:
            options = {p["type"]: p for p in prix if p["indice"] == indice
                       and p["echeance"] == date and float(p["moneyness"]) == 1}
            lignes.append([indice, DATES.get(date, date)] + [
                fr(options[type_option][methode], 2)
                for type_option in ("call", "put")
                for methode in ("controle", "europeenne")
            ])
    y = tableau(pdf, y, ("Indice", "Échéance 2027", "Call asi.", "Call euro.", "Put asi.", "Put euro."),
                lignes, (0.13, 0.18, 0.1725, 0.1725, 0.1725, 0.1725), hauteur=17)
    signe = sum(float(p["ecart_pb_spot"]) < 0 for p in prix)
    y = paragraphe(
        pdf, f"L'asiatique est moins chère dans <b>{signe} cas sur {len(prix)}</b> sur cette grille. "
        "Les prix européens utilisent les mêmes paramètres et l'échéance de chaque contrat.",
        y - 8, taille=9.1, leading=12,
    )
    if y < 58:
        raise ValueError("Le contenu de la page 1 dépasse l'espace disponible.")
    pdf.showPage()


def _limites(valeurs):
    bas = math.floor(math.log10(min(valeurs)))
    haut = math.ceil(math.log10(max(valeurs)))
    return bas, max(bas + 1, haut)


def graphique(pdf, x, haut, largeur, indice, mesures, limites_x, limites_y):
    texte(pdf, x, haut, indice, taille=11, police="Helvetica-Bold")
    bx, by, l, h = x + 34, haut - 129, largeur - 44, 113
    xmin, xmax = limites_x
    ymin, ymax = limites_y

    def echelle(valeur, bas, maximum):
        return (math.log10(valeur) - bas) / (maximum - bas)

    for puissance in range(ymin, ymax + 1):
        yy = by + h * (puissance - ymin) / (ymax - ymin)
        trait(pdf, bx, yy, bx + l, yy)
        centre(pdf, bx - 17, yy - 2.5, f"{10**puissance:g}", taille=7.5, couleur=TEXTE)
    for puissance in range(xmin, xmax + 1):
        xx = bx + l * (puissance - xmin) / (xmax - xmin)
        trait(pdf, xx, by, xx, by + h)
        centre(pdf, xx, by - 12, f"{10**puissance:g}", taille=7.5, couleur=TEXTE)
    yy = by + h * echelle(1, ymin, ymax)
    pdf.saveState()
    pdf.setDash(3, 2)
    trait(pdf, bx, yy, bx + l, yy, ENCRE)
    pdf.restoreState()
    for methode, (_, couleur) in METHODES.items():
        lignes = sorted(
            (r for r in mesures if r["indice"] == indice and r["methode"] == methode),
            key=lambda r: int(r["simulations"]),
        )
        points = [
            (bx + l * echelle(float(r["temps_ms"]), xmin, xmax),
             by + h * echelle(float(r["demi_ic95_max_pb"]), ymin, ymax))
            for r in lignes if r["demi_ic95_max_pb"] and float(r["demi_ic95_max_pb"]) > 0
        ]
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            trait(pdf, x1, y1, x2, y2, couleur)
        pdf.setFillColor(couleur)
        for xp, yp in points:
            pdf.circle(xp, yp, 3.0, stroke=0, fill=1)
    centre(pdf, bx + l / 2, by - 25, "Temps médian (ms)", taille=8, couleur=TEXTE)


def page_performance(pdf, performance, convergence, sensibilite, marche):
    entete(pdf, 2, "Réduire l'erreur de simulation", "Précision et coût au strike égal au spot")
    y = section(pdf, H - 139, "03", "Contrôle géométrique et coût de calcul")
    y = paragraphe(
        pdf, "Le générateur congruentiel de L'Ecuyer et Box-Muller alimentent la simulation "
        "exacte entre les fixings. On calcule le payoff géométrique Y sur les mêmes "
        "trajectoires que le payoff arithmétique X. Le lot pilote estime bêta. "
        "Le prix contrôlé est la moyenne de X - bêta × (Y - E[Y]), où E[Y] est analytique.",
        y, taille=9.7, leading=13,
    )
    y = paragraphe(
        pdf, "<b>Demi-IC à 95 % en pb du spot.</b> Chaque point indique une taille de simulation. "
        "Les axes sont logarithmiques. Le trait pointillé marque la cible de 1 pb.",
        y - 10, taille=9.1, leading=12,
    )
    positives = [r for r in convergence if r["demi_ic95_max_pb"] and float(r["demi_ic95_max_pb"]) > 0]
    limites_x = _limites([float(r["temps_ms"]) for r in positives])
    limites_y = _limites([1.0] + [float(r["demi_ic95_max_pb"]) for r in positives])
    largeur = (LARGEUR - 18) / 2
    haut = y - 18
    for i, indice in enumerate(INDICES):
        graphique(pdf, MARGE + i * (largeur + 18), haut, largeur,
                  indice, positives, limites_x, limites_y)
    y = haut - 171
    for i, (_, (libelle, couleur)) in enumerate(METHODES.items()):
        x = MARGE + 34 + 82 * i
        rectangle(pdf, x, y - 1, 11, 6, couleur)
        texte(pdf, x + 16, y - 1, libelle, taille=8.5, couleur=TEXTE)
    y = section(pdf, y - 22, "04", "Temps pour une précision comparable")
    lignes = [
        (r["indice"], METHODES[r["methode"]][0], fr(r["simulations"]), fr(r["pilote"]),
         fr(r["temps_ms"], 1), fr(r["demi_ic95_max_pb"], 2) if r["demi_ic95_max_pb"] else "n.d.",
         "Oui" if r["cible_atteinte"] == "True" else "Non")
        for r in performance
    ]
    y = tableau(pdf, y, ("Indice", "Méthode", "Trajectoires", "Pilote",
                          "Temps (ms)", "Demi-IC (pb)", "Cible"),
                lignes, (0.1, 0.16, 0.17, 0.125, 0.15, 0.16, 0.135))
    gains = []
    for indice in INDICES:
        cas = {r["methode"]: r for r in performance if r["indice"] == indice}
        if all(v["cible_atteinte"] == "True" for v in cas.values()):
            gain = float(cas["naive"]["temps_ms"]) / float(cas["controle"]["temps_ms"])
            gains.append(f"<b>{indice} ×{fr(gain, 1)}</b>")
    conclusion = (" La cible est atteinte avec un gain de temps de " + " et ".join(gains) + "."
                  if gains else "")
    y = paragraphe(
        pdf, "Mesures au 31 mars 2027. Temps médian pilote compris. "
        "La demi-largeur retient le maximum call-put sur les répétitions." + conclusion,
        y - 8, taille=8.8, leading=11.7,
    )
    cas = max(sensibilite, key=lambda r: abs(float(r["ecart_historique_implicite_pb"])))
    temoin = marche["actifs"][0]["echeances"][0]["diagnostic"]
    y = paragraphe(
        pdf, f"<b>Sensibilité aux entrées.</b> Pour le {cas['type']} {cas['indice']} central, "
        f"passer de {fr(100 * float(cas['volatilite_implicite']), 2)} % de volatilité implicite "
        f"à {fr(100 * float(cas['volatilite_historique']), 2)} % de volatilité historique "
        f"déplace le prix de {fr(abs(float(cas['ecart_historique_implicite_pb'])), 1)} pb du spot. "
        f"Sur SPX en janvier, {temoin['temoins_dans_spread']}/{temoin['temoins_total']} prix "
        "européens témoins sont dans leur fourchette avec la volatilité constante.",
        y - 11, taille=9.1, leading=12,
    )
    y = paragraphe(
        pdf, '<link href="https://www.cboe.com/markets/us/options/market-statistics/product-data/'
        'proprietary-index-marking-prices/">Cboe</link> · '
        '<link href="https://www.federalreserve.gov/data/nominal-yield-curve.htm">Fed</link> · '
        '<link href="https://doi.org/10.1090/S0025-5718-99-00996-5">L\'Ecuyer (1999)</link> · '
        '<link href="https://doi.org/10.1016/0378-4266(90)90039-5">Kemna et Vorst (1990)</link>',
        y - 8, taille=8.1, leading=10, couleur=SARCELLE,
    )
    if y < 57:
        raise ValueError("Le contenu de la page 2 dépasse l'espace disponible.")
    pdf.showPage()


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--resultats", type=Path, default=Path("resultats"))
    analyseur.add_argument("--donnees", type=Path, default=Path("data/market_snapshot.json"))
    analyseur.add_argument("--sortie", type=Path, default=Path("rapport/sujet_2.pdf"))
    args = analyseur.parse_args()
    prix, performance, convergence, sensibilite = (
        lire_csv(args.resultats, nom) for nom in
        ("prix.csv", "performance.csv", "convergence.csv", "sensibilite.csv")
    )
    marche = json.loads(args.donnees.read_text(encoding="utf-8"))
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    pdf = Canvas(str(args.sortie), pagesize=A4, pageCompression=1, invariant=1)
    pdf.setTitle("Prycing - Sujet 2")
    pdf.setSubject("Valorisation des options asiatiques sur SPX et RUT")
    page_prix(pdf, prix, marche)
    page_performance(pdf, performance, convergence, sensibilite, marche)
    pdf.save()
    print(f"Rapport écrit dans {args.sortie}")


if __name__ == "__main__":
    main()
