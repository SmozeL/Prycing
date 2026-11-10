# Prycing · Options asiatiques sur indices

Projet de pricing sur le S&P 500 et le Russell 2000, avec une date de valorisation commune au **30 octobre 2026**. Les contrats asiatiques sont définis pour l'étude et valorisés sous Black-Scholes. Le projet compare le Monte-Carlo naïf et le contrôle par payoff géométrique aux européennes équivalentes.

## Lancer l’étude

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[rapport]'
python run_tp.py
```

Dans VS Code, ouvrir le dossier du dépôt, sélectionner l'interpréteur de `.venv`, puis cliquer sur **Run Python File** dans `run_tp.py`. Le script lit le relevé calibré versionné, écrit les CSV et les PNG dans `resultats/`, puis ouvre les deux figures Matplotlib.

À chaque lancement, le script tire une nouvelle graine et l'inscrit dans le terminal et dans `prix.csv`. Les prix Monte-Carlo fluctuent avec les trajectoires simulées. Les prix européens, calculés par formule, sont déterminés par les seules entrées du marché. Pour rejouer les mêmes trajectoires avec les mêmes réglages, passer la graine affichée avec `--graine`. Les chronos restent sensibles à la machine et à sa charge.

```bash
python run_tp.py --graine 42
python run_tp.py --graine 42 --sans-affichage
```

`--sans-affichage` enregistre les graphiques sans ouvrir de fenêtres. Si le projet est déjà installé, relancer `python -m pip install -e '.[rapport]'` pour ajouter Matplotlib.

```bash
python -m unittest discover -s tests -v
python -m asian_pricing.rapport --resultats resultats --sortie resultats/sujet_2.pdf
```

Le [rapport de deux pages](rapport/sujet_2.pdf) et les [CSV qui ont servi à le produire](rapport/resultats) sont versionnés. Pour reconstruire le rapport publié, passer `--resultats rapport/resultats` au générateur.

## Utiliser le pricer

```python
from asian_pricing import pricer_asiatique

prix = pricer_asiatique(
    spot=100, strike=100, volatilite=0.20, taux=0.03, maturite=1.0,
    dividende=0.01, frequence=12, simulations=50_000, pilote=5_000,
)
print(prix["call"]["controle"]["prix"], prix["put"]["controle"]["ic"])
```

Les taux et la volatilité sont annuels et saisis en décimal. `frequence` donne le nombre de fixings par an. Pour des séances irrégulières, passer `dates_observation` en années depuis la valorisation. Le pricer expose `naive` et `controle` pour chaque type d'option, ainsi que le prix européen de référence.

## Données et hypothèses

- Les indices **SPX** et **RUT** partagent la devise USD et ont des compositions différentes. Les dates du 29 janvier, du 31 mars et du 30 juin 2027 correspondent à des échéances communes de séries à règlement PM.
- Le relevé `data/market_snapshot.json` contient les données d'entrée calculées, les paramètres, le calendrier et la provenance. Les cotations brutes du fichier d'échange restent des entrées locales.
- On estime le forward sur des paires call-put comparables et la volatilité implicite près du forward. Le rendement du dividende est déduit du portage implicite. La courbe Treasury estimée par la Fed sert de proxy d'actualisation. Chaque couple indice-échéance utilise une volatilité constante commune aux trois strikes.
- Les observations mensuelles correspondent aux séances retenues dans le relevé. Le temps est exprimé en années **ACT/365F**. La moyenne donne le même poids à chaque fixing futur. Le paiement intervient à l'échéance.

Sources officielles des entrées de marché.

- [Cotations et prix indicatifs Cboe](https://www.cboe.com/markets/us/options/market-statistics/product-data/proprietary-index-marking-prices/)
- [Historique SPX](https://cdn.cboe.com/api/global/us_indices/daily_prices/SPX_History.csv) · [Historique RUT](https://cdn.cboe.com/api/global/us_indices/daily_prices/RUT_History.csv)
- [Courbe nominale de la Fed](https://www.federalreserve.gov/data/nominal-yield-curve.htm)

Pour recalibrer à partir des quatre CSV d'origine conservés dans un dossier local, utiliser `python -m asian_pricing.donnees --csv-dir CHEMIN --output resultats/market_snapshot.json`. Le fichier de cotations Cboe est remplacé périodiquement. Les empreintes dans l'instantané identifient les fichiers de la session utilisée.

## Méthode et lecture des sorties

Le pricer simule les transitions exactes de Black-Scholes entre fixings, avec les normales produites par un générateur congruentiel multiplicatif de L'Ecuyer et Box-Muller. Pour le contrôle, la moyenne des log-cours est gaussienne. Sa variance tient compte des temps de constatation. Le prix géométrique analytique sert à centrer le contrôle. Le lot pilote estime le coefficient de contrôle, et le lot de production fournit les prix et leurs erreurs types.

- `prix.csv` donne les 18 scénarios, avec les calls et les puts, les prix européens, les deux estimateurs asiatiques et leurs IC à 95 %.
- `performance.csv` compare les temps médians et les demi-largeurs d'IC effectivement obtenues sur les contrats centraux, pour une cible de 1 point de base du spot. Le coût du pilote est inclus. Le champ `cible_atteinte` signale le résultat de la mesure.
- `convergence.csv` donne le coût et la précision sur plusieurs tailles de simulation.
- `sensibilite.csv` mesure l'effet du passage de la volatilité implicite à la volatilité historique sur les mêmes contrats centraux. Cette variation de prix et l'incertitude Monte-Carlo sont présentées séparément.
- `comparaison_prix.png` compare les primes asiatiques contrôlées et européennes par indice, type d'option, strike relatif et échéance.
- `precision_temps.png` place les deux méthodes sur le même graphique pour chaque indice. Les axes logarithmiques montrent le temps médian et la demi-largeur maximale des IC à 95 %, avec une cible de 1 point de base du spot.

Le chronométrage dépend de la machine. Les intervalles asymptotiques mesurent l'erreur d'échantillonnage sous Black-Scholes avec les paramètres retenus. Les diagnostics sur options européennes décrivent le calibrage des entrées du modèle.

[L'Ecuyer, 1999](https://doi.org/10.1090/S0025-5718-99-00996-5) · [Box et Muller, 1958](https://doi.org/10.1214/aoms/1177706645) · [Kemna et Vorst, 1990](https://doi.org/10.1016/0378-4266(90)90039-5)
