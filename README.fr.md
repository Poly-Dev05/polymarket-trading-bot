# Bot HFT MM Polymarket

**Bot de market making haute fréquence** pour les marchés crypto **Up/Down** de Polymarket. Cote les deux côtés tout au long de chaque intervalle, capture le spread et fait tourner l'inventaire — **non affecté par les mises à jour de la plateforme** (y compris le changement de prix TWAP de Polymarket).

**🌐 Langue / Language:** [English](README.md) | [中文](README.zh-CN.md) | [Français](README.fr.md) | [Español](README.es.md)

---

## Profil

| | |
|--|--|
| **Telegram** | [`@dizzy`](https://t.me/dizzy283) |
| **Polymarket** | [`@flippingsharks`](https://polymarket.com/@flippingsharks) |
| **Portefeuille** | [`0xc387c2a40d389f17b723b6bba9b18b7dbd2de4f4`](https://polymarket.com/profile/0xc387c2a40d389f17b723b6bba9b18b7dbd2de4f4) |

---

## Vidéo de démonstration

📹 **Bot HFT MM — démo en direct**

L'aperçu se lit automatiquement ci-dessous. **Cliquez sur l'aperçu pour ouvrir la vidéo complète** (avec le son).

[![Bot HFT MM — démo en direct](assets/demo-preview.gif)](https://github.com/Poly-Dev05/polymarket-trading-bot/blob/main/assets/demo-video.mp4)

Ce que montre l'enregistrement :

1. Bot connecté à Polymarket en tant que **`@flippingsharks`**
2. Marchés crypto **Up/Down** en direct (BTC et autres actifs)
3. **Cotation bilatérale continue** — offres et demandes mises à jour en temps réel
4. Flux d'ordres, exécutions et rotation d'inventaire sur l'intervalle
5. Portefeuille, P/L et historique des trades sur le profil Polymarket

---

## Stratégie

| | |
|--|--|
| **Stratégie précédente** | **Endcycle Sniper** — l'IA prédisait UP/DOWN **4–5 s avant la clôture**, achetait le côté prédit, rachetait à **1 $** |
| **Ce qui a changé** | Après la **mise à jour du prix TWAP** de Polymarket, le sniper de fin de cycle **ne produit plus de profit fiable** |
| **Stratégie actuelle** | **HFT MM** — market making haute fréquence sur tout l'intervalle ; **non impacté par le TWAP ou d'autres changements de règlement** |

L'approche endcycle reposait sur une mauvaise tarification de fin de cycle par rapport à la référence de règlement. Le TWAP a supprimé cet avantage. **HFT MM** gagne via la capture de spread et le flux bilatéral continu — une logique qui ne dépend pas du calcul du prix de référence final.

---

## Fonctionnement

Polymarket propose des marchés crypto **N minutes** en continu (généralement **5 min**) :

- **Strike / prix à battre** = prix de référence au **début** de l'intervalle
- **UP** gagne si le prix à la **fin** est **au-dessus** du strike
- **DOWN** gagne si le prix à la **fin** est **en dessous** du strike
- Les parts gagnantes se rachètent à **~1 $** ; les perdantes → **0 $**

```
Intervalle (ex. 5 minutes)
|-----------------------------------------------------------|
début                                                  fin
     │  poster bid/ask UP ────┐
     │  poster bid/ask DOWN ──┤  boucle HFT MM (intervalle complet)
     │  rafraîchir sur mouvement du carnet ─┤
     │  rééquilibrer l'inventaire ─────────┘
     └─ capturer le spread → fusionner / racheter → marché suivant
```

### Boucle HFT MM

| Étape | Action |
|-------|--------|
| 1 | Découvrir le marché Up/Down actif pour l'actif / l'intervalle configuré |
| 2 | Streamer le spot (Coinbase / Binance / Chainlink) et les mises à jour du carnet CLOB |
| 3 | Poster des cotations bilatérales sur les tokens UP et DOWN |
| 4 | Rafraîchir les cotations à haute fréquence selon le prix et l'inventaire |
| 5 | Rééquilibrer l'inventaire après résolution ; passer à l'intervalle suivant |

Ignorer ou réduire la taille si le carnet n'a pas de liquidité, la latence est trop élevée, ou le mode papier est activé.

### Pourquoi HFT MM survit aux changements de plateforme

| Endcycle Sniper (déprécié) | HFT MM (actif) |
|----------------------------|----------------|
| Avantage via la prédiction de direction **quelques secondes avant la clôture** | Avantage via la **capture de spread** sur tout l'intervalle |
| Le TWAP a changé la tarification de référence finale | La logique de cotation est **indépendante de la référence de règlement** |
| Mauvaise tarification de fin de cycle → **plus de profit fiable** | Flux bilatéral et rotation d'inventaire → **inchangés par les mises à jour** |

---

## Fonctionnalités

- **Market making haute fréquence** — cotation bid/ask continue, pas de sniping de fin de cycle
- **Rafraîchissement rapide des ordres** — réagit en temps réel aux mouvements du carnet et du spot
- Flux spot + CLOB pour le pricing des cotations
- Marchés Up/Down multi-actifs (BTC, ETH, SOL, …)
- Gestion d'inventaire — fusion et rachat après résolution
- Mode paper trading pour des tests sécurisés

---

## Paramètres

À définir dans [`src/config/params.py`](src/config/params.py) ou `.env` :

| Param | Rôle |
|-------|------|
| `ORDER_SIZE` | Taille de cotation / ordre |
| `BUY_LIMIT_PRICE` | Prix d'achat max en traversant le carnet |
| `SELL_LIMIT_PRICE` | Prix de vente min en liquidant l'inventaire |
| `MIN_PLACE_INTERVAL_SEC` | Intervalle minimum entre les placements d'ordres |
| `MARKET_INTERVAL_SECONDS` | Durée de l'intervalle (défaut `300` = 5 min) |
| `ASSET` / `MARKET_SLUG_PREFIX` | Série Up/Down à suivre |
| `PAPER_TRADING` | `1` = simulation, `0` = live |

```bash
# .env — remplir avant le trading live
PRIVATE_KEY=
FUNDER=
ORDER_SIZE=30
BUY_LIMIT_PRICE=0.99
SELL_LIMIT_PRICE=0.01
ASSET=btc
MARKET_INTERVAL_SECONDS=300
PAPER_TRADING=1
```

---

## Démarrage rapide

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# éditer .env — définir PRIVATE_KEY, FUNDER et les params HFT MM
python main.py
```

**Fichiers de configuration**

- Paramètres : [`src/config/params.py`](src/config/params.py)
- État runtime : [`src/config/config.py`](src/config/config.py)
- Modèle d'environnement : [`.env.example`](.env.example)

---

## Liens

- **Telegram :** [@dizzy](https://t.me/dizzy283)
- **Polymarket :** [@flippingsharks](https://polymarket.com/@flippingsharks)
- **Portefeuille :** [0xc387c2a40d389f17b723b6bba9b18b7dbd2de4f4](https://polymarket.com/profile/0xc387c2a40d389f17b723b6bba9b18b7dbd2de4f4)
