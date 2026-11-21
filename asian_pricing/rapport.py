"""Compose le rapport de deux pages à partir des CSV du script d'étude."""

import argparse
import csv
import json
import math
from datetime import date
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
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


def _police(pdf, nom):
    return getattr(pdf, "_polices_prycing", {}).get(nom, nom)


def texte(pdf, x, y, valeur, *, taille=10, police="Helvetica", couleur=ENCRE):
    pdf.setFillColor(couleur)
    pdf.setFont(_police(pdf, police), taille)
    pdf.drawString(x, y, valeur)


def centre(pdf, x, y, valeur, *, taille=9, couleur=ENCRE, gras=False):
    pdf.setFillColor(couleur)
    pdf.setFont(_police(pdf, "Helvetica-Bold" if gras else "Helvetica"), taille)
    pdf.drawCentredString(x, y, valeur)


def paragraphe(pdf, html, y, *, taille=10, leading=14, couleur=TEXTE):
    style = ParagraphStyle(
        "rapport", fontName=_police(pdf, "Helvetica"), fontSize=taille,
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


def entete(pdf, numero, titre, sous_titre, releve="30 octobre 2026"):
    rectangle(pdf, MARGE, H - 47, 23, 3, SARCELLE)
    texte(pdf, MARGE + 32, H - 48, "PRYCING  /  PROJET ING 4  /  SUJET 2",
          taille=9, police="Helvetica-Bold", couleur=SARCELLE)
    texte(pdf, MARGE, H - 93, titre, taille=32, police="Times-Roman")
    texte(pdf, MARGE, H - 112, sous_titre, taille=10, couleur=TEXTE)
    trait(pdf, MARGE, 46, W - MARGE, 46)
    texte(pdf, MARGE, 30, f"Relevé de marché du {releve}", taille=8, couleur=TEXTE)
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


def graphique(pdf, x, haut, largeur, indice, mesures, limites_x, limites_y, *, titre=None, cible=1.0):
    texte(pdf, x, haut, titre or indice, taille=11, police="Helvetica-Bold")
    bx, by, l, h = x + 34, haut - 129, largeur - 44, 113
    xmin, xmax = limites_x
    ymin, ymax = limites_y

    def echelle(valeur, bas, maximum):
        return (math.log10(valeur) - bas) / (maximum - bas)

    for puissance in range(ymin, ymax + 1):
        yy = by + h * (puissance - ymin) / (ymax - ymin)
        trait(pdf, bx, yy, bx + l, yy)
        centre(pdf, bx - 17, yy - 2.5, fr(10**puissance, max(0, -puissance)),
               taille=7.5, couleur=TEXTE)
    for puissance in range(xmin, xmax + 1):
        xx = bx + l * (puissance - xmin) / (xmax - xmin)
        trait(pdf, xx, by, xx, by + h)
        centre(pdf, xx, by - 12, fr(10**puissance, max(0, -puissance)), taille=7.5, couleur=TEXTE)
    yy = by + h * echelle(cible, ymin, ymax)
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


def _date_courte(iso):
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def _source_lien(url, libelle):
    return f'<link href="{escape(url, quote=True)}">{escape(libelle)}</link>'


def _incorporer_polices_spy(pdf):
    recherches = (
        (Path("/System/Library/Fonts/Supplemental"), "Arial.ttf", "Arial Bold.ttf",
         "Arial Italic.ttf", "Times New Roman.ttf"),
        (Path("/usr/share/fonts/truetype/dejavu"), "DejaVuSans.ttf", "DejaVuSans-Bold.ttf",
         "DejaVuSans-Oblique.ttf", "DejaVuSerif.ttf"),
        (Path("C:/Windows/Fonts"), "arial.ttf", "arialbd.ttf", "ariali.ttf", "times.ttf"),
    )
    alias = ("PrycingSans", "PrycingSansBold", "PrycingSansItalic", "PrycingSerif")
    for repertoire, *fichiers in recherches:
        chemins = [repertoire / fichier for fichier in fichiers]
        if all(chemin.is_file() for chemin in chemins):
            for nom, chemin in zip(alias, chemins):
                pdfmetrics.registerFont(TTFont(nom, str(chemin)))
            pdfmetrics.registerFontFamily(alias[0], normal=alias[0], bold=alias[1], italic=alias[2])
            pdf._polices_prycing = dict(zip(
                ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Times-Roman"), alias,
            ))
            break


def couverture_spy(pdf):
    rectangle(pdf, 0, H - 11, W, 11, SARCELLE)
    texte(pdf, MARGE, H - 78, "PROJET PRICING  /  ING 4", taille=11,
          police="Helvetica-Bold", couleur=SARCELLE)
    texte(pdf, W - MARGE - 58, H - 78, "2026–2027", taille=11, couleur=TEXTE)
    trait(pdf, MARGE, H - 98, W - MARGE, H - 98)
    texte(pdf, MARGE, H - 175, "Valorisation des", taille=44, police="Times-Roman")
    texte(pdf, MARGE, H - 225, "options asiatiques", taille=44, police="Times-Roman")
    paragraphe(pdf, "Monte-Carlo et contrôle géométrique sur le SPDR S&amp;P 500 ETF Trust (SPY)",
               H - 256, taille=17, leading=23)
    texte(pdf, MARGE, H - 354, "Énoncé 2  ·  Python", taille=13,
          police="Helvetica-Bold", couleur=SARCELLE)
    trait(pdf, MARGE, H - 411, W - MARGE, H - 411)
    texte(pdf, MARGE, H - 443, "Membres du groupe", taille=13, police="Helvetica-Bold")
    colonne = LARGEUR / 2
    for i in range(10):
        x = MARGE + (i // 5) * colonne
        y = H - 500 - (i % 5) * 34
        texte(pdf, x, y + 8, str(i + 1), taille=9, couleur=TEXTE)
        pdf.acroForm.textfield(
            name=f"Membre {i + 1}", tooltip=f"Prénom et nom du membre {i + 1}",
            x=x + 24, y=y, width=colonne - 33, height=24, fontSize=11,
            textColor=ENCRE, fillColor=FOND, borderColor=GRIS, borderWidth=0.5,
            borderStyle="underlined", forceBorder=True, fieldFlags="", maxlen=60,
        )
    pdf.showPage()


def _prime_spy(ligne):
    bas, haut = ligne["ic95_inf_controle"], ligne["ic95_sup_controle"]
    h = f" ± {fr((float(haut) - float(bas)) / 2, 3)}" if bas and haut else " *"
    return fr(ligne["controle"], 3) + h


def _tableau_prix_spy(pdf, y, prix):
    paires = {}
    for ligne in prix:
        cle = (ligne["echeance"], float(ligne["strike"]))
        paires.setdefault(cle, {})[ligne["type"]] = ligne
    lignes = []
    precedente = None
    for (echeance, strike), paire in sorted(paires.items()):
        call, put = paire["call"], paire["put"]
        lignes.append((
            _date_courte(echeance) if echeance != precedente else "",
            fr(100 * float(call["moneyness"])) + " %", fr(strike, 2),
            _prime_spy(call), fr(call["europeenne"], 3),
            _prime_spy(put), fr(put["europeenne"], 3),
        ))
        precedente = echeance
    return tableau(
        pdf, y, ("Échéance", "K/spot", "K", "Call asiatique ± h", "Call euro.",
                 "Put asiatique ± h", "Put euro."), lignes,
        (0.15, 0.092, 0.11, 0.199, 0.125, 0.199, 0.125), hauteur=16,
    )


def page_prix_spy(pdf, prix, marche):
    actif, = marche["actifs"]
    echeance = actif["echeances"][0]
    spot, taux, q, sigma = actif["spot"], echeance["taux"], echeance["dividende"], echeance["volatilite"]
    releve = _date_courte(marche["date_valorisation"])
    entete(pdf, 1, "Valoriser les options sur SPY",
           "Calls et puts asiatiques à moyenne arithmétique", releve)
    y = H - 137
    rectangle(pdf, MARGE, y - 42, LARGEUR, 42, FOND)
    for i, (libelle, valeur) in enumerate((
        ("CLÔTURE SPY", fr(spot, 2) + " USD"), ("VOLATILITÉ", fr(100 * sigma, 2) + " %"),
        ("TAUX SANS RISQUE", fr(100 * taux, 2) + " %"), ("DIVIDENDE CONTINU", fr(100 * q, 2) + " %"),
    )):
        x = MARGE + 10 + i * LARGEUR / 4
        texte(pdf, x, y - 13, libelle, taille=7.8, police="Helvetica-Bold", couleur=SARCELLE)
        texte(pdf, x, y - 31, valeur, taille=14)
    y = paragraphe(
        pdf, "SPY réplique le S&amp;P 500. Le fonds offre un sous-jacent coté et diversifié, "
        "avec un cours et des distributions observables. On retient le Treasury américain à un an "
        "comme proxy du taux continu, et le VIX1Y, construit sur les options du S&amp;P 500, "
        "comme proxy de volatilité implicite. "
        f"Le rendement q rapporte les distributions 2025 ({fr(spot * q, 5)} USD/part) au spot. "
        "Ces entrées sont maintenues constantes pour toutes les échéances.",
        y - 52, taille=9.45, leading=12.3,
    )
    y = section(pdf, y - 19, "01", "Simulation et comparaison avec l’européenne")
    y = paragraphe(
        pdf, "Les trajectoires suivent Black–Scholes sous la mesure risque-neutre. Le pricer simule exactement "
        "les incréments de log S, de moyenne (r − q − σ²/2) × pas et de variance σ² × pas. "
        "Les observations se font à la dernière séance du mois (ACT/365F), échéance incluse et spot initial exclu. "
        "On actualise à l’échéance "
        "le payoff du call ou du put sur la moyenne arithmétique. Les primes européennes utilisent le spot terminal "
        "et les mêmes paramètres. Les contrats de la grille sont théoriques.",
        y, taille=9.45, leading=12.3,
    )
    y = paragraphe(
        pdf, f"<b>Primes et strikes en USD par part.</b> Prix asiatiques avec contrôle, ± demi-IC à 95 %. "
        f"{fr(prix[0]['simulations'])} trajectoires de production et {fr(prix[0]['pilote'])} au pilote.",
        y - 7, taille=9.1, leading=11.8,
    )
    y = _tableau_prix_spy(pdf, y - 5, prix)
    if any(r["ic95_inf_controle"] == "" for r in prix):
        y = paragraphe(pdf, "* IC omis lorsque l’échantillon donne trop peu de payoffs informatifs.",
                       y - 5, taille=8.5, leading=10.5)
    y = section(pdf, y - 16, "02", "Effet du strike et de la maturité")
    monnaie = [r for r in prix if math.isclose(float(r["moneyness"]), 1.0)]
    call_court, *_, call_long = sorted((r for r in monnaie if r["type"] == "call"),
                                       key=lambda r: r["echeance"])
    inf = sum(float(r["ecart_points"]) < 0 for r in prix)
    inversions = [r for r in prix if r["type"] == "put" and float(r["ecart_points"]) > 0]
    precision = "La plus faible dispersion de la moyenne pèse sur les primes autour de la monnaie."
    if inversions:
        cas = max(inversions, key=lambda r: float(r["ecart_points"]))
        precision = (
            f"À K = {fr(cas['strike'], 2)} et à l’échéance du {_date_courte(cas['echeance'])}, "
            f"le put asiatique dépasse le put européen de {fr(cas['ecart_points'], 2)} USD. "
            "Pour un put très dans la monnaie, l’espérance de la moyenne, plus basse que celle "
            "du spot terminal (r > q), peut dominer l’effet de la dispersion."
        )
    y = paragraphe(
        pdf, f"L’asiatique est moins chère dans {inf} contrats sur {len(prix)}. Au strike égal au spot, "
        f"l’écart européen moins asiatique du call passe de {fr(-float(call_court['ecart_points']), 2)} "
        f"à {fr(-float(call_long['ecart_points']), 2)} USD entre la première et la dernière échéance. "
        + precision, y, taille=9.45, leading=12.3,
    )
    if y < 57:
        raise ValueError("Le contenu de la page 1 SPY dépasse l’espace disponible.")
    pdf.showPage()


def page_performance_spy(pdf, performance, convergence, sensibilite, marche):
    actif, = marche["actifs"]
    spot = actif["spot"]
    cible = float(performance[0]["cible_pb"])
    releve = _date_courte(marche["date_valorisation"])
    entete(pdf, 2, "Mesurer la réduction de variance",
           "Contrôle géométrique et temps à précision cible", releve)
    y = section(pdf, H - 138, "03", "Variable de contrôle")
    y = paragraphe(
        pdf, "Les normales standard proviennent du générateur congruentiel de L’Ecuyer (64 bits) "
        "suivi de Box–Muller. À chaque trajectoire correspondent les payoffs actualisés X "
        "(moyenne arithmétique) et Y (géométrique), de même strike et de même sens. "
        "Le lot pilote estime β = Cov(X,Y)/Var(Y). Sur le lot de production, on moyenne "
        "X − β(Y − E[Y]).",
        y, taille=9.45, leading=12.3,
    )
    y = paragraphe(
        pdf, "Le logarithme de la moyenne géométrique est normal, de moyenne "
        "log S<sub>0</sub> + (r − q − σ²/2) × moyenne des dates. Pour M fixings, la variance est "
        "σ² × Σ<sub>j</sub> [(M − j + 1)/M]² × pas<sub>j</sub>, car l’incrément j est compté "
        "M − j + 1 fois. L’espérance de Y se calcule par la formule du payoff sur lognormale, "
        "actualisée à T. La demi-largeur de l’IC vaut 1,96 × erreur-type.",
        y - 7, taille=9.45, leading=12.3,
    )
    y = section(pdf, y - 18, "04", "Précision et coût au strike égal au spot")
    mesure = {r["methode"]: r for r in performance}
    date_test = _date_courte(performance[0]["echeance"])
    repetitions = int(performance[0]["repetitions"])
    protocole = f"Temps médian sur {repetitions} répétitions" if repetitions > 1 else "Un essai par méthode"
    y = paragraphe(
        pdf, f"Échéance du {date_test}. {protocole}, pilote compris. "
        "La demi-largeur retient le maximum sur les calls, puts et répétitions. "
        f"Le trait pointillé indique la cible de {fr(cible)} pb du spot ({fr(cible * spot / 10_000, 4)} USD).",
        y, taille=9.2, leading=12,
    )
    positives = [r for r in convergence if r["demi_ic95_max_pb"] and float(r["demi_ic95_max_pb"]) > 0]
    limites_x = _limites([float(r["temps_ms"]) for r in positives])
    limites_y = _limites([cible] + [float(r["demi_ic95_max_pb"]) for r in positives])
    haut = y - 18
    graphique(pdf, MARGE, haut, LARGEUR, "SPY", positives, limites_x, limites_y,
              titre="Demi-IC à 95 % (pb du spot) · échelles logarithmiques", cible=cible)
    y = haut - 170
    for i, (_, (libelle, couleur)) in enumerate(METHODES.items()):
        x = MARGE + 34 + 83 * i
        rectangle(pdf, x, y, 11, 6, couleur)
        texte(pdf, x + 16, y, libelle, taille=8.5, couleur=TEXTE)

    n = max(int(r["simulations"]) for r in convergence)
    meme_n = {r["methode"]: r for r in convergence if int(r["simulations"]) == n}
    largeur_naif = float(meme_n["naive"]["demi_ic95_max_pb"])
    largeur_cv = float(meme_n["controle"]["demi_ic95_max_pb"])
    y = paragraphe(
        pdf, f"À {fr(n)} trajectoires, le contrôle divise la demi-largeur maximale par "
        f"{fr(largeur_naif / largeur_cv, 1)}. Son temps médian est de "
        f"{fr(meme_n['controle']['temps_ms'], 1)} ms contre {fr(meme_n['naive']['temps_ms'], 1)} ms "
        "pour le Monte-Carlo naïf à même taille de production.",
        y - 10, taille=9.2, leading=12,
    )
    lignes = [
        (METHODES[r["methode"]][0], fr(r["simulations"]), fr(r["pilote"]), fr(r["temps_ms"], 1),
         fr(r["demi_ic95_max_pb"], 2) if r["demi_ic95_max_pb"] else "n.d.",
         "Oui" if r["cible_atteinte"] == "True" else "Non")
        for r in performance
    ]
    y = tableau(pdf, y - 6, ("Méthode", "Trajectoires", "Pilote", "Temps (ms)", "Demi-IC (pb)", "Cible atteinte"),
                lignes, (0.16, 0.18, 0.15, 0.17, 0.17, 0.17), hauteur=17)
    if all(r["cible_atteinte"] == "True" for r in performance):
        gain = float(mesure["naive"]["temps_ms"]) / float(mesure["controle"]["temps_ms"])
        conclusion = f" Les deux méthodes atteignent la cible. Sur cette machine, le contrôle réduit le temps d’un facteur {fr(gain, 1)}."
    else:
        conclusion = " La cible commune n’est pas atteinte par toutes les méthodes sur cet essai."
    y = paragraphe(
        pdf, "Les tailles du tableau sont dimensionnées sur un échantillon séparé, avec une marge de 10 %."
        + conclusion, y - 6, taille=9.2, leading=12,
    )
    if sensibilite:
        cas = max(sensibilite, key=lambda r: abs(float(r["ecart_historique_implicite_pb"])))
        decalage = float(cas["ecart_historique_implicite_pb"]) * spot / 10_000
        verbe = "réduit" if decalage < 0 else "augmente"
        y = paragraphe(
            pdf, f"<b>Sensibilité.</b> Pour le {cas['type']} à la monnaie, remplacer la volatilité "
            f"de référence de {fr(100 * float(cas['volatilite_implicite']), 2)} % par la volatilité "
            f"historique de {fr(100 * float(cas['volatilite_historique']), 2)} % "
            f"(250 log-rendements quotidiens de VL, annualisés) {verbe} la prime de {fr(abs(decalage), 2)} USD.",
            y - 7, taille=9.2, leading=12,
        )
    sources = marche.get("sources", {})
    liens = [_source_lien(sources[cle]["url"], libelle) for cle, libelle in (
        ("spot_sec", "Clôture SPY (SEC)"),
        ("distributions", "Distributions (State Street)"),
        ("volatilite_vix1y", "VIX1Y (Cboe)"),
        ("taux_treasury", "Treasury 1 an"),
        ("historique_vl", "VL (State Street)"),
    ) if cle in sources]
    if liens:
        y = paragraphe(pdf, "Données : " + " · ".join(liens), y - 7,
                       taille=8.15, leading=10.2, couleur=SARCELLE)
    y = paragraphe(
        pdf, "Méthodes : A. W. Sanoussi Mani, <i>Pricing Monte Carlo</i>, p. 7–12, 22, 35 et 48–51, 76–77 · "
        + _source_lien("https://doi.org/10.1090/S0025-5718-99-00996-5", "L’Ecuyer (1999)"),
        y - 5, taille=8.15, leading=10.2, couleur=SARCELLE,
    )
    if y < 57:
        raise ValueError("Le contenu de la page 2 SPY dépasse l’espace disponible.")
    pdf.showPage()


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--resultats", type=Path, default=Path("resultats"))
    analyseur.add_argument("--donnees", type=Path, default=Path("data/spy_snapshot.json"))
    analyseur.add_argument("--sortie", type=Path, default=Path("resultats/sujet_2.pdf"))
    args = analyseur.parse_args()
    prix, performance, convergence, sensibilite = (
        lire_csv(args.resultats, nom) for nom in
        ("prix.csv", "performance.csv", "convergence.csv", "sensibilite.csv")
    )
    marche = json.loads(args.donnees.read_text(encoding="utf-8"))
    symboles = [actif["symbole"] for actif in marche["actifs"]]
    if {ligne["indice"] for ligne in prix} != set(symboles):
        analyseur.error("Les actifs des résultats et de l’instantané de marché doivent coïncider.")
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    pdf = Canvas(str(args.sortie), pagesize=A4, pageCompression=1, invariant=1)
    pdf.setTitle("Prycing - Sujet 2")
    pdf.setSubject("Valorisation des options asiatiques sur " + ", ".join(symboles))
    if symboles == ["SPY"]:
        _incorporer_polices_spy(pdf)
        couverture_spy(pdf)
        page_prix_spy(pdf, prix, marche)
        page_performance_spy(pdf, performance, convergence, sensibilite, marche)
    else:
        page_prix(pdf, prix, marche)
        page_performance(pdf, performance, convergence, sensibilite, marche)
    pdf.save()
    print(f"Rapport écrit dans {args.sortie}")


if __name__ == "__main__":
    main()
