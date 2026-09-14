# Bot HFT MM de Polymarket

**Bot de market making de alta frecuencia** para mercados crypto **Up/Down** de Polymarket. Cota ambos lados durante cada intervalo, captura el spread y rota inventario — **no afectado por actualizaciones de la plataforma** (incluido el cambio de precio TWAP de Polymarket).

**🌐 Idioma / Language:** [English](README.md) | [中文](README.zh-CN.md) | [Français](README.fr.md) | [Español](README.es.md)

---

## Perfil

| | |
|--|--|
| **Telegram** | [`@dizzy`](https://t.me/dizzy283) |
| **Polymarket** | [`@flippingsharks`](https://polymarket.com/@flippingsharks) |
| **Wallet** | [`0xc387c2a40d389f17b723b6bba9b18b7dbd2de4f4`](https://polymarket.com/profile/0xc387c2a40d389f17b723b6bba9b18b7dbd2de4f4) |

---

## Video de demostración

📹 **Bot HFT MM — demo en vivo**

<video src="assets/demo-video.mp4" controls width="100%"></video>

Lo que muestra la grabación:

1. Bot conectado a Polymarket como **`@flippingsharks`**
2. Mercados crypto **Up/Down** en vivo (BTC y otros activos)
3. **Cotización bilateral continua** — bids y asks actualizándose en tiempo real
4. Flujo de órdenes, fills y rotación de inventario durante el intervalo
5. Portafolio, P/L e historial de trades en el perfil de Polymarket

---

## Estrategia

| | |
|--|--|
| **Estrategia anterior** | **Endcycle Sniper** — la IA predecía UP/DOWN **4–5 s antes del cierre**, compraba el lado predicho, rescataba a **$1** |
| **Qué cambió** | Tras la **actualización del precio TWAP** de Polymarket, el sniper de fin de ciclo **ya no genera beneficio fiable** |
| **Estrategia actual** | **HFT MM** — market making de alta frecuencia en todo el intervalo; **no impactado por TWAP u otros cambios de liquidación** |

El enfoque endcycle dependía de una mala valoración al final del ciclo respecto a la referencia de liquidación. TWAP eliminó esa ventaja. **HFT MM** gana con captura de spread y flujo bilateral continuo — lógica que no depende de cómo se calcula el precio de referencia final.

---

## Cómo funciona

Polymarket ejecuta mercados crypto de **N minutos** en rotación (normalmente **5 min**):

- **Strike / precio a batir** = precio de referencia al **inicio** del intervalo
- **UP** gana si el precio al **final** está **por encima** del strike
- **DOWN** gana si el precio al **final** está **por debajo** del strike
- Las participaciones ganadoras se rescatan a **~$1**; las perdedoras → **$0**

```
Intervalo (ej. 5 minutos)
|-----------------------------------------------------------|
inicio                                                 fin
     │  publicar bid/ask UP ────┐
     │  publicar bid/ask DOWN ──┤  bucle HFT MM (intervalo completo)
     │  refrescar con movimiento del libro ─┤
     │  reequilibrar inventario ────────────┘
     └─ capturar spread → fusionar / rescatar → siguiente mercado
```

### Bucle HFT MM

| Paso | Acción |
|------|--------|
| 1 | Descubrir el mercado Up/Down activo para el activo / intervalo configurado |
| 2 | Transmitir spot (Coinbase / Binance / Chainlink) y actualizaciones del libro CLOB |
| 3 | Publicar cotizaciones bilaterales en tokens UP y DOWN |
| 4 | Refrescar cotizaciones a alta frecuencia según precio e inventario |
| 5 | Reequilibrar inventario tras la resolución; pasar al siguiente intervalo |

Omitir o reducir tamaño si el libro no tiene liquidez, la latencia es alta o el modo paper está activo.

### Por qué HFT MM sobrevive a los cambios de plataforma

| Endcycle Sniper (obsoleto) | HFT MM (activo) |
|----------------------------|-----------------|
| Ventaja al predecir dirección **segundos antes del cierre** | Ventaja por **captura de spread** en todo el intervalo |
| TWAP cambió la valoración de referencia final | La lógica de cotización es **independiente de la referencia de liquidación** |
| Mala valoración al final del ciclo → **sin beneficio fiable** | Flujo bilateral y rotación de inventario → **sin cambios por actualizaciones** |

---

## Características

- **Market making de alta frecuencia** — cotización bid/ask continua, no sniping de fin de ciclo
- **Refresco rápido de órdenes** — reacciona en tiempo real a movimientos del libro y del spot
- Feeds spot + CLOB para pricing de cotizaciones
- Mercados Up/Down multi-activo (BTC, ETH, SOL, …)
- Gestión de inventario — fusionar y rescatar tras la resolución
- Modo paper trading para pruebas seguras

---

## Parámetros

Configurar en [`src/config/params.py`](src/config/params.py) o `.env`:

| Parámetro | Rol |
|-----------|-----|
| `ORDER_SIZE` | Tamaño de cotización / orden |
| `BUY_LIMIT_PRICE` | Precio máximo de compra al cruzar el libro |
| `SELL_LIMIT_PRICE` | Precio mínimo de venta al liquidar inventario |
| `MIN_PLACE_INTERVAL_SEC` | Intervalo mínimo entre colocaciones de órdenes |
| `MARKET_INTERVAL_SECONDS` | Duración del intervalo (por defecto `300` = 5 min) |
| `ASSET` / `MARKET_SLUG_PREFIX` | Serie Up/Down a seguir |
| `PAPER_TRADING` | `1` = simular, `0` = live |

```bash
# .env — completar antes de trading en vivo
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

## Inicio rápido

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# editar .env — definir PRIVATE_KEY, FUNDER y params HFT MM
python main.py
```

**Archivos de configuración**

- Ajustes: [`src/config/params.py`](src/config/params.py)
- Estado en runtime: [`src/config/config.py`](src/config/config.py)
- Plantilla de entorno: [`.env.example`](.env.example)

---

## Enlaces

- **Telegram:** [@dizzy](https://t.me/dizzy283)
- **Polymarket:** [@flippingsharks](https://polymarket.com/@flippingsharks)
- **Wallet:** [0xc387c2a40d389f17b723b6bba9b18b7dbd2de4f4](https://polymarket.com/profile/0xc387c2a40d389f17b723b6bba9b18b7dbd2de4f4)
