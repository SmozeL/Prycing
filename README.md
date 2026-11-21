# Options asiatiques sur Alphabet (GOOGL)

**Projet Pricing ING 4 · Énoncé 2**

Le projet valorise des calls et puts asiatiques à moyenne arithmétique sous Black–Scholes. Il compare le Monte-Carlo brut, le Monte-Carlo avec contrôle géométrique et le prix analytique de l’option européenne correspondante.

## Exécution

Avec Python 3.9 ou supérieur, depuis la racine du dépôt.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python run_tp.py --graine 2026 --sans-affichage --sortie resultats/googl
```

Dans VS Code, sélectionner l’interpréteur de `.venv`, puis lancer **Reproduire l’étude GOOGL** avec **Ctrl+F5** pour mesurer les temps sans débogueur. Le profil utilise les mêmes paramètres que la commande, une graine de 2026 et le dossier `resultats/googl/`. Un lancement sans `--graine` tire une nouvelle graine et l’affiche dans le terminal. Les prix sont reproductibles à graine et réglages identiques. Les chronos dépendent de la machine et de sa charge.

```bash
python -m unittest discover -s tests -v
```

## Données et conventions

L’action **Alphabet de classe A**, cotée au Nasdaq sous le symbole **GOOGL**, fournit un sous-jacent liquide avec des clôtures et des dividendes documentés. La date de valorisation est le **31 décembre 2025**. L’[instantané de marché](data/googl_snapshot.json) fige les entrées, les échéances et les fixings. L’exécution est indépendante du réseau.

- **Spot de 313,00 USD.** Cours de clôture du 31 décembre 2025. [Relevé déposé auprès de la SEC](https://www.sec.gov/Archives/edgar/data/200245/000191870426000167/form424b2.htm)
- **Taux de 3,48 %.** Rendement du Treasury à un an utilisé comme approximation d’un taux continu constant. [U.S. Treasury](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve&field_tdr_date_value=2025)
- **Dividende continu approximé à 0,26518 %.** Total de 0,83 USD déclaré par action en 2025, divisé par le spot. [Alphabet, formulaire 10-K 2025](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm)
- **Volatilité historique annualisée de 32,23 %.** Écart-type d’échantillon de 250 log-rendements journaliers, multiplié par √252. La fenêtre s’étend de la clôture du 31 décembre 2024 à celle du 31 décembre 2025. L’analyse de sensibilité utilise les 63 derniers rendements de cette série, soit 29,77 %. [Série historique de Nasdaq](https://api.nasdaq.com/api/quote/GOOGL/chart?assetclass=stocks&fromdate=2024-12-31&todate=2025-12-31)

La grille combine cinq strikes à 80 %, 90 %, 100 %, 110 % et 140 % du spot et trois échéances à environ 6, 12 et 24 mois. Les contrats asiatiques sont définis pour l’étude. Les dates sont en ACT/365F. La moyenne équipondère les clôtures de la dernière séance de chaque mois, échéance incluse. Le paiement intervient à l’échéance et le spot initial est exclu de la moyenne. Les prix sont en USD par action.

## Méthode de valorisation

1. **Simulation.** Sous la mesure risque-neutre, la transition en logarithme est exacte entre les dates de fixing.

   ```math
   \log S_{t_j} = \log S_{t_{j-1}}
     + (r-q-\sigma^2/2)\Delta t_j + \sigma\sqrt{\Delta t_j}\,Z_j
   ```

   Le générateur congruentiel multiplicatif de L’Ecuyer fournit les uniformes. Box–Muller les transforme par paires en normales standard. Le pricer calcule ensuite la moyenne arithmétique $A$ et le payoff actualisé, call $e^{-rT}(A-K)^+$ ou put $e^{-rT}(K-A)^+$.

2. **Contrôle géométrique.** Pour les mêmes fixings, $\log G$ est la moyenne des logarithmes de spot et suit une loi normale. L’incrément brownien du pas $i$ apparaît dans $m-i+1$ des $m$ observations, d’où sa contribution $\sigma^2 [(m-i+1)/m]^2\Delta t_i$ à la variance de $\log G$. Cette loi donne le prix analytique du payoff géométrique $Y$, actualisé à $T$.

3. **Estimateur et précision.** Un lot pilote estime $\widehat\beta=\operatorname{Cov}(X,Y)/\operatorname{Var}(Y)$, où $X$ est le payoff arithmétique actualisé. La production utilise un sous-flux disjoint. Elle moyenne $X$ pour le prix brut et $X-\widehat\beta(Y-\mathbb{E}[Y])$ pour le prix contrôlé. La demi-largeur de l’IC asymptotique à 95 % est $1{,}96\,s/\sqrt{N}$, calculée sur les valeurs qui alimentent l’estimateur. L’IC mesure le bruit Monte-Carlo pour le modèle et les entrées retenus.

4. **Référence européenne et contrôles.** La référence Black–Scholes utilise le spot à l’échéance au lieu de la moyenne. Avec un seul fixing à $T$, l’asiatique contrôlée retrouve le prix européen. Les tests couvrent également la volatilité nulle, les grilles irrégulières et une comparaison avec une intégration numérique indépendante pour deux fixings.

Références méthodologiques · A. W. Sanoussi Mani, *Pricing Monte Carlo ING4 FIN, S1 2026*, p. 7–12, 22, 35, 42–44, 48–51 et 76–77. [L’Ecuyer, 1999](https://doi.org/10.1090/S0025-5718-99-00996-5) · [Box et Muller, 1958](https://doi.org/10.1214/aoms/1177706645)

## Lire les résultats

- `prix.csv` contient les 30 comparaisons, les primes brutes et contrôlées, les prix européens et géométriques, les IC et les diagnostics de contrôle.
- `convergence.csv` compare les temps et la précision à taille de production égale. `performance.csv` compare les temps médians pour atteindre une demi-largeur de **5 points de base du spot**, soit **0,1565 USD par action** pour GOOGL. L’essai retient la plus grande demi-largeur sur les calls, les puts et les répétitions. Le temps de calcul contrôlé inclut son lot pilote. La taille est estimée sur un échantillon séparé, avec une marge de 10 % et un minimum de 1 024 trajectoires.
- `sensibilite.csv` compare les primes contrôlées à la monnaie entre les deux fenêtres de volatilité en réutilisant les mêmes tirages. `comparaison_prix.png` et `precision_temps.png` visualisent les comparaisons de prix et de précision.

## Structure du code

| Module | Rôle |
| --- | --- |
| `contrats.py` | Validation des paramètres et construction des dates d’observation |
| `rng.py` | Générateur congruentiel, sous-flux et transformation de Box–Muller |
| `black_scholes.py` | Moments de la moyenne géométrique et formules analytiques |
| `pricer.py` | Simulation par lots, payoffs, estimateurs et intervalles de confiance |
| `donnees.py` | Chargement de l’instantané |
| `experiences.py` et `figures.py` | Grille, sensibilité, chronométrage, CSV et graphiques |
| `run_tp.py` | Interface en ligne de commande |
| `calibrage_indices.py` | Utilitaire indépendant pour l’ancien instantané SPX/RUT |

Pour appeler le pricer directement, les taux et la volatilité s’expriment en décimal, les maturités en années et la fréquence en observations par an.

```python
from asian_pricing import pricer_asiatique

prix = pricer_asiatique(
    spot=313.0, strike=313.0, volatilite=0.322302066636,
    taux=0.0348, maturite=1.0, dividende=0.83 / 313.0,
    frequence=12, simulations=50_000, pilote=5_000, graine=2026,
)
print(prix["call"]["controle"]["prix"])
print(prix["put"]["controle"]["ic"])
```

Passer `dates_observation` en fractions d’année pour utiliser un calendrier précis à la place de `frequence`. Pour chaque type d’option, `pricer_asiatique` expose `naive`, `controle`, `europeenne` et `geometrique`. Le [jeu d’essai SPX/RUT](data/market_snapshot.json) se charge avec `--donnees data/market_snapshot.json`.
