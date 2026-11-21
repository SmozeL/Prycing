# Options asiatiques sur Alphabet (GOOGL)

Projet Pricing ING 4 · Énoncé 2

## Lancer le projet

Depuis le dossier du projet, avec Python 3.9 ou supérieur.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_tp.py
```

Dans VS Code, sélectionner l’interpréteur de `.venv`, ouvrir `run_tp.py` et cliquer sur **Run Python File**, ou lancer la commande dans le terminal. Chaque exécution tire et affiche une nouvelle graine. Utiliser `python run_tp.py --graine 2026` pour rejouer la graine 2026 et `--sortie dossier` pour choisir où écrire les CSV.

`asian_pricing.py` contient le pricer. `run_tp.py` contient les données de l’étude. Le terminal affiche les 18 comparaisons de prix et les gains de précision et de temps. Les résultats détaillés sont exportés dans `resultats/prix.csv` et `resultats/performance.csv` sans connexion réseau.

## Sous-jacent et hypothèses

GOOGL est l’action de classe A d’Alphabet. Elle est cotée au Nasdaq et dispose d’un historique public de cours et de dividendes. Les paramètres sont figés au **31 décembre 2025**.

- **Spot de 313,00 USD.** Clôture à la date de valorisation. [Document déposé auprès de la SEC](https://www.sec.gov/Archives/edgar/data/200245/000191870426000167/form424b2.htm)
- **Taux de 3,48 %.** Le rendement du Treasury à un an sert de proxy du taux continu constant. [U.S. Treasury](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve&field_tdr_date_value=2025)
- **Dividende de 0,26518 %.** Les 0,83 USD par action déclarés en 2025 sont divisés par le spot pour estimer le rendement continu. [Alphabet, formulaire 10-K 2025](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm)
- **Volatilité historique de 32,23 %.** Écart-type d’échantillon de 250 log-rendements de clôture du 31 décembre 2024 au 31 décembre 2025, annualisé par √252. [Clôtures Nasdaq](https://api.nasdaq.com/api/quote/GOOGL/chart?assetclass=stocks&fromdate=2024-12-31&todate=2025-12-31)

Les contrats théoriques combinent trois strikes (90 %, 100 % et 110 % du spot) et trois échéances (environ 6, 12 et 24 mois). Les fixings sont les dernières séances de chaque mois, échéance incluse et spot initial exclu. Le temps est compté en ACT/365F et les primes en USD par action. [Calendrier Nasdaq](https://www.nasdaqtrader.com/Trader.aspx?id=Calendar)

## Les quatre questions de l’énoncé

1. **Valorisation.** Le générateur congruentiel de L’Ecuyer et Box–Muller fournissent les normales. On simule la transition exacte de Black–Scholes entre deux fixings et on moyenne les payoffs actualisés du call et du put sur la moyenne arithmétique. [L’Ecuyer](https://doi.org/10.1090/S0025-5718-99-00996-5) · [Box et Muller](https://doi.org/10.1214/aoms/1177706645)
2. **Comparaison.** `prix.csv` contient 18 comparaisons entre primes asiatiques brutes et contrôlées et primes européennes de Black–Scholes, ainsi que les demi-largeurs d’IC à 95 % des estimateurs Monte-Carlo.
3. **Contrôle géométrique.** On corrige le payoff arithmétique actualisé $X$ par le payoff géométrique actualisé $Y$, d’espérance analytique. Un lot pilote estime $\beta=\mathrm{Cov}(X,Y)/\mathrm{Var}(Y)$, puis un lot disjoint estime la moyenne de $X-\beta(Y-\mathbb{E}[Y])$.
4. **Précision et temps.** `performance.csv` compare les demi-largeurs d’IC à **50 000 trajectoires** et les temps médians pour atteindre une demi-largeur cible de **0,1565 USD** (5 points de base du spot), à la monnaie à un an. Le dimensionnement ajoute 10 % de marge avec un minimum de 2 000 trajectoires. Le temps du contrôle inclut le pilote. Le gain de temps se lit lorsque les deux méthodes atteignent la cible.

## Appeler le pricer

La maturité est en années. Les taux et la volatilité sont en décimal. Fournir `dates_observation` en fractions d’année pour utiliser un calendrier explicite.

```python
from asian_pricing import pricer_asiatique

resultat = pricer_asiatique(
    spot=313, strike=313, volatilite=0.322302066636,
    taux=0.0348, maturite=1, dividende=0.83 / 313,
    frequence=12, graine=2026,
)
print(resultat["call"]["controle"]["prix"])
```
