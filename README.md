# Prycing · Options asiatiques sur SPY

Projet Python de valorisation de calls et puts asiatiques à moyenne arithmétique sur **SPY**, le fonds coté State Street SPDR S&P 500 ETF Trust. Le relevé est arrêté au **31 décembre 2025**. Le pricer compare le Monte-Carlo brut, le Monte-Carlo avec contrôle géométrique et la formule de Black-Scholes pour les européennes équivalentes.

## Lancer l’étude dans VS Code

Dans le terminal du dossier, créer un environnement local et installer le projet.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[rapport]'
```

Dans VS Code, choisir l’interpréteur de `.venv` et le profil **Reproduire l’étude SPY**, puis lancer sans débogueur (**Ctrl+F5**) pour mesurer les temps. La configuration fixe la graine à 2026. Le terminal affiche les résultats à la monnaie et la comparaison des temps. Les quatre CSV et les deux graphiques sont enregistrés dans `resultats/`.

```bash
python run_tp.py --graine 2026 --sans-affichage
python -m unittest discover -s tests -v
```

Sans `--graine`, le script tire une nouvelle graine, puis l’inscrit dans le terminal et dans `prix.csv`. Sans `--sans-affichage`, il ouvre les figures en plus de les enregistrer. Les prix et les intervalles sont reproductibles avec les mêmes paramètres et la même graine. Les chronos varient selon la machine et sa charge.

Le [rapport SPY](rapport/spy/sujet_2.pdf) comporte une garde remplissable pour dix membres et deux pages de résultats. Les [mesures utilisées dans le rapport](rapport/spy/resultats) sont versionnées.

```bash
python -m asian_pricing.rapport --donnees data/spy_snapshot.json \
  --resultats resultats --sortie resultats/sujet_2.pdf
```

## Données du 31 décembre 2025

SPY est un ETF coté en USD qui suit le S&P 500. Sa liquidité et la disponibilité de son historique permettent de documenter les entrées. Les 30 primes de l’étude couvrent cinq strikes (80 %, 90 %, 100 %, 110 % et 140 % du spot), trois échéances (environ 6 mois, 1 an et 2 ans) et les deux types d’option.

- **Spot de 681,92 USD par part.** Cours de clôture du 31 décembre 2025. [Relevé déposé auprès de la SEC](https://www.sec.gov/Archives/edgar/data/895421/000183988226009753/ms14199_424b2-06009.htm)
- **Taux annuel de 3,48 %.** Rendement Treasury à un an utilisé comme approximation d’un taux continu constant pour les trois échéances. [U.S. Treasury](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve&field_tdr_date_value=2025)
- **Dividende continu de 1,06774 %.** Somme des distributions 2025 de 7,28113 USD par part, divisée par le spot. [Historique des distributions State Street](https://www.ssga.com/library-content/products/fund-data/etfs/us/spdr-etf-historical-distributions.xlsx)
- **Volatilité de référence de 22,54 %.** Clôture du VIX1Y, fondé sur les options de l’indice S&P 500, utilisée comme approximation constante de la volatilité de SPY. [Historique Cboe](https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX1Y_History.csv)
- **Sensibilité à 18,61 %.** Écart-type d’échantillon de 250 log-rendements journaliers de la valeur liquidative, du 31 décembre 2024 au 31 décembre 2025, annualisé par √252. [Historique de la valeur liquidative de State Street](https://www.ssga.com/library-content/products/fund-data/etfs/us/navhist-us-en-spy.xlsx)

Les paramètres, dates et sources sont figés dans [l’instantané SPY](data/spy_snapshot.json). Les options asiatiques sont des contrats définis pour l’étude. Leur moyenne arithmétique équipondère les clôtures de la dernière séance de chaque mois, échéance incluse. Les fractions d’année sont en ACT/365F, et le payoff est payé à l’échéance.

## Utiliser le pricer

```python
from asian_pricing import pricer_asiatique

prix = pricer_asiatique(
    spot=681.92, strike=681.92, volatilite=0.2254, taux=0.0348, maturite=1.0,
    dividende=7.28113 / 681.92, frequence=12, simulations=50_000, pilote=5_000,
    graine=2026,
)
print(prix["call"]["controle"]["prix"], prix["put"]["controle"]["ic"])
```

Les taux et la volatilité sont annuels et saisis en décimal. `frequence` donne le nombre de fixings par an. Passer `dates_observation` en fractions d’année pour une grille irrégulière. Pour chaque type d’option, le pricer retourne les estimations `naive` et `controle` ainsi que les références `europeenne` et `geometrique`.

Les transitions exactes de Black-Scholes entre fixings utilisent des normales produites par un générateur congruentiel multiplicatif de L’Ecuyer et Box-Muller. Le prix analytique du payoff géométrique centre la variable de contrôle. Un lot pilote estime le coefficient, puis un lot de production disjoint fournit les prix et les intervalles de confiance à 95 %.

- `prix.csv` rassemble les primes, les intervalles de confiance et les diagnostics du contrôle.
- `performance.csv` compare les temps médians et les demi-largeurs maximales observées à une cible commune de cinq points de base du spot (environ 0,34 USD par part). Le coût du pilote est inclus.
- `convergence.csv` suit le coût et la précision à nombre de trajectoires égal. `sensibilite.csv` montre l’effet d’une volatilité réalisée de 18,61 %.
- `comparaison_prix.png` et `precision_temps.png` visualisent ces résultats. Les intervalles mesurent l’erreur d’échantillonnage pour les paramètres et le modèle retenus.

## Étude SPX et RUT

L’étude précédente sur les indices reste accessible avec son propre jeu de données et son rapport. Les conventions de calibration sont décrites dans [l’instantané SPX/RUT](data/market_snapshot.json). [Rapport SPX/RUT](rapport/sujet_2.pdf)

```bash
python run_tp.py --donnees data/market_snapshot.json --graine 42 --sans-affichage \
  --sortie resultats/indices
python -m asian_pricing.rapport --donnees data/market_snapshot.json \
  --resultats resultats/indices --sortie resultats/indices/sujet_2.pdf
```

L’instantané de ces indices peut être recalibré à partir des quatre CSV d’origine, avec `python -m asian_pricing.donnees --csv-dir CHEMIN --output resultats/market_snapshot.json`. Le fichier de cotations Cboe est remplacé périodiquement. Les empreintes de l’instantané identifient les fichiers de la session utilisée.

[L’Ecuyer, 1999](https://doi.org/10.1090/S0025-5718-99-00996-5) · [Box et Muller, 1958](https://doi.org/10.1214/aoms/1177706645) · [Kemna et Vorst, 1990](https://doi.org/10.1016/0378-4266(90)90039-5)
