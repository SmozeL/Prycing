# Options asiatiques sur Alphabet (GOOGL)

**Projet Pricing ING 4 · Énoncé 2**

Valorisation de calls et de puts asiatiques à moyenne arithmétique sous Black–Scholes. L’étude compare le Monte-Carlo brut et le Monte-Carlo avec contrôle géométrique au prix de l’option européenne de même strike et de même échéance.

## Exécution

Depuis la racine du dépôt, avec Python 3.9 ou supérieur.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python run_tp.py --graine 2026
```

Dans VS Code, sélectionner l’interpréteur de `.venv`, puis lancer **Reproduire l’étude GOOGL** avec **Ctrl+F5**. Les deux lancements écrivent les CSV dans `resultats/etude_googl/`. Les prix sont reproductibles à graine identique. Sans `--graine`, une nouvelle graine est tirée et affichée.

## Données de marché

L’action de classe A d’Alphabet (GOOGL) est valorisée au **31 décembre 2025**. Cotée au Nasdaq, elle fournit des historiques de clôtures et de dividendes accessibles. L’[instantané GOOGL](data/googl_snapshot.json) contient les entrées du modèle et permet une exécution hors ligne.

- **Spot de 313,00 USD.** Clôture de l’action au 31 décembre 2025. [Document déposé auprès de la SEC](https://www.sec.gov/Archives/edgar/data/200245/000191870426000167/form424b2.htm)
- **Taux de 3,48 %.** Le rendement du Treasury à un an sert d’approximation du taux continu constant. [U.S. Treasury](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve&field_tdr_date_value=2025)
- **Rendement du dividende d’environ 0,26518 %.** Les 0,83 USD déclarés par action en 2025 sont divisés par le spot pour obtenir un taux continu approximatif. [Alphabet, formulaire 10-K 2025](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm)
- **Volatilité historique de 32,23 %.** Écart-type empirique de 250 log-rendements journaliers du 31 décembre 2024 au 31 décembre 2025, annualisé par √252. [Historique Nasdaq](https://api.nasdaq.com/api/quote/GOOGL/chart?assetclass=stocks&fromdate=2024-12-31&todate=2025-12-31)

Les contrats théoriques couvrent **trois strikes** (90 %, 100 % et 110 % du spot) et **trois maturités** (environ 6, 12 et 24 mois). La moyenne équipondère les clôtures de la dernière séance de chaque mois, échéance incluse et spot initial exclu. Les temps sont comptés en ACT/365F, le payoff est réglé à l’échéance et les primes sont exprimées en USD par action.

## Méthode

Le générateur congruentiel de L’Ecuyer fournit les uniformes, puis Box–Muller les transforme en normales standard. La transition Black–Scholes est simulée exactement en logarithme entre deux fixings. Chaque trajectoire fournit un payoff arithmétique actualisé $X$ et un payoff géométrique actualisé $Y$. [L’Ecuyer, 1999](https://doi.org/10.1090/S0025-5718-99-00996-5) · [Box et Muller, 1958](https://doi.org/10.1214/aoms/1177706645)

La moyenne brute estime l’espérance de $X$. Le lot pilote estime $\widehat\beta=\operatorname{Cov}(X,Y)/\operatorname{Var}(Y)$. Sur un lot de production disjoint, on moyenne $X-\widehat\beta(Y-\mathbb{E}[Y])$. Le logarithme de la moyenne géométrique suit une loi normale, ce qui donne $\mathbb{E}[Y]$ analytiquement. L’erreur-type Monte-Carlo est $s/\sqrt{N}$ pour l’estimateur considéré. La demi-largeur de l’IC asymptotique à 95 % vaut environ $1{,}96\,s/\sqrt{N}$.

## Résultats

- **`prix.csv`** contient les **18 comparaisons** (trois strikes × trois maturités × deux types d’option), avec les primes brutes, contrôlées et européennes et les demi-largeurs d’IC disponibles. On reconstitue chaque IC en retranchant et en ajoutant sa demi-largeur au prix estimé.
- **`performance.csv`** contient **quatre lignes** pour le strike à la monnaie et l’échéance à un an. Le régime `trajectoires_egales` compare les deux méthodes à production égale. Le régime `precision_cible` vise une demi-largeur d’IC à 95 % de **5 points de base du spot**, soit **0,1565 USD par action**. Le fichier donne le temps médian et les demi-largeurs maximales par type d’option sur les répétitions. Le chronométrage de la méthode contrôlée inclut son lot pilote. Les temps dépendent de la machine et de sa charge.

## Appel Python et tests

Le pricer calcule les deux types d’option. Les taux et la volatilité s’expriment en décimal, la maturité en années. Une liste `dates_observation` en fractions d’année permet de fournir le calendrier à la place de la fréquence.

```python
from asian_pricing import pricer_asiatique

resultat = pricer_asiatique(
    spot=313.0, strike=313.0, volatilite=0.322302066636,
    taux=0.0348, maturite=1.0, dividende=0.83 / 313.0,
    frequence=12, simulations=50_000, pilote=5_000, graine=2026,
)
print(resultat["call"]["controle"]["prix"])
```

```bash
python -m unittest discover -s tests -v
```
