"""Figures Matplotlib de comparaison des primes et du coût de simulation."""

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter


_ENCRE = "#233448"
_GRILLE = "#dbe4ed"
_METHODES = {
    "naive": ("Monte-Carlo naïf", "#a8471a"),
    "controle": ("Contrôle géométrique", "#00766f"),
}


def _style(axe, titre):
    axe.set_title(titre, loc="left", fontweight="bold", color=_ENCRE)
    axe.set_axisbelow(True)
    axe.grid(True, color=_GRILLE, linewidth=0.7)
    axe.spines[["top", "right"]].set_visible(False)


def _comparaison_prix(prix):
    indices = list(dict.fromkeys(ligne["indice"] for ligne in prix))
    echeances = sorted({ligne["echeance"] for ligne in prix})
    strikes = sorted({round(ligne["moneyness"], 10) for ligne in prix})
    palette = plt.get_cmap("Dark2")
    couleurs = {date: palette(i % palette.N) for i, date in enumerate(echeances)}
    figure, axes = plt.subplots(
        len(indices), 2, figsize=(11, 2.9 * len(indices) + 1.3),
        layout="constrained", sharex=True, sharey=True, squeeze=False,
    )
    figure.suptitle("Primes asiatiques et européennes", fontsize=16, fontweight="bold")

    for indice, ligne_axes in zip(indices, axes):
        for option, axe in zip(("call", "put"), ligne_axes):
            _style(axe, f"{indice} · {option.capitalize()}")
            axe.set_xticks(strikes)
            axe.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
            for date, couleur in couleurs.items():
                cas = sorted(
                    (r for r in prix if (r["indice"], r["type"], r["echeance"])
                     == (indice, option, date)),
                    key=lambda r: r["moneyness"],
                )
                x = [r["moneyness"] for r in cas]
                asiatique = [10_000 * r["controle"] / r["spot"] for r in cas]
                europeenne = [10_000 * r["europeenne"] / r["spot"] for r in cas]
                axe.plot(x, asiatique, color=couleur, marker="o", linewidth=2)
                axe.plot(x, europeenne, color=couleur, linestyle="--", linewidth=1.7)
        ligne_axes[0].set_ylabel("Prime (pb du spot)")

    for axe in axes[-1]:
        axe.set_xlabel("Strike / spot initial")
    legende = [Line2D([], [], color=couleur, linewidth=3, label=date)
               for date, couleur in couleurs.items()]
    legende.extend((
        Line2D([], [], color=_ENCRE, marker="o", label="Asiatique (contrôle)"),
        Line2D([], [], color=_ENCRE, linestyle="--", label="Européenne"),
    ))
    figure.legend(handles=legende, loc="outside lower center", ncols=min(5, len(legende)),
                  frameon=False)
    return figure


def _ic_positif(ligne):
    largeur = ligne["demi_ic95_max_pb"]
    return largeur is not None and largeur > 0 and ligne["temps_ms"] > 0


def _precision_temps(convergence, performance):
    indices = list(dict.fromkeys(ligne["indice"] for ligne in convergence))
    cible = performance[0]["cible_pb"]
    figure, (axes,) = plt.subplots(
        1, len(indices), figsize=(5.5 * len(indices), 5.1),
        layout="constrained", sharex=True, sharey=True, squeeze=False,
    )
    figure.suptitle(
        "Précision Monte-Carlo en fonction du temps\n"
        "Strike = spot initial · IC maximal sur calls, puts et répétitions",
        fontsize=14, fontweight="bold",
    )

    for indice, axe in zip(indices, axes):
        lignes = [r for r in convergence if r["indice"] == indice]
        _style(axe, f"{indice} · échéance {lignes[0]['echeance']}")
        axe.set(xscale="log", yscale="log", xlabel="Temps médian (ms, pilote inclus)")
        axe.axhline(cible, color=_ENCRE, linewidth=1, linestyle=":")
        for methode, (_, couleur) in _METHODES.items():
            mesures = sorted(
                (r for r in lignes if r["methode"] == methode and _ic_positif(r)),
                key=lambda r: r["simulations"],
            )
            axe.plot([r["temps_ms"] for r in mesures],
                     [r["demi_ic95_max_pb"] for r in mesures],
                     color=couleur, marker="o", linewidth=2)
            for r in performance:
                if r["indice"] == indice and r["methode"] == methode and _ic_positif(r):
                    axe.scatter(r["temps_ms"], r["demi_ic95_max_pb"], marker="D", s=62,
                                color=couleur, edgecolors="white", zorder=3)

        toutes = lignes + [r for r in performance if r["indice"] == indice]
        if any(not _ic_positif(r) for r in toutes):
            axe.text(0.02, 0.02, "IC nuls ou indisponibles omis", transform=axe.transAxes,
                     fontsize=8, color=_ENCRE)

    axes[0].set_ylabel("Demi-largeur de l’IC à 95 % (pb du spot)")
    legende = [Line2D([], [], color=couleur, marker="o", label=nom)
               for nom, couleur in _METHODES.values()]
    legende.extend((
        Line2D([], [], color=_ENCRE, linestyle="none", marker="D", label="Essai ciblé"),
        Line2D([], [], color=_ENCRE, linestyle=":", label=f"Cible de {cible:g} pb"),
    ))
    figure.legend(handles=legende, loc="outside lower center", ncols=4, frameon=False)
    return figure


def creer_figures(resultats):
    """Construit les figures à partir des mêmes données que les exports CSV."""
    return {
        "comparaison_prix": _comparaison_prix(resultats["prix"]),
        "precision_temps": _precision_temps(resultats["convergence"], resultats["performance"]),
    }
