# Market Health Indicators Reference

This document defines key indicators for assessing market health, their acceptable ranges, and suggested mitigations when values fall outside those ranges.

---

## 1. Liquidity Indicators

### Bid-Ask Spread %

**Definition:** `(best_ask - best_bid) / mid_price × 100`

**Raw metrics:** `exchange_best_bid`, `exchange_best_ask`

| Range | Status | Interpretation |
|-------|--------|----------------|
| < 0.5% | Excellent | Very liquid, tight spreads |
| 0.5% - 3% | Healthy | Normal trading conditions |
| 3% - 5% | Warning | Reduced liquidity, higher trading costs |
| > 5% | Critical | Illiquid, trading expensive |

**Mitigations:**
- Incentivize market makers with rebates
- Reduce minimum tick size
- Add liquidity provider bots

---

### Order Book Depth

**Definition:** Total volume within 5% of mid-price, as % of float

**Raw metrics:** `exchange_bid_volume`, `exchange_ask_volume`, `exchange_float_shares`

| Range | Status | Interpretation |
|-------|--------|----------------|
| > 20% | Excellent | Deep book, resilient to large orders |
| 10% - 20% | Healthy | Adequate depth |
| 5% - 10% | Warning | Thin book, vulnerable to price swings |
| < 5% | Critical | Very thin, easily manipulated |

**Mitigations:**
- Add more market participants
- Encourage limit orders over market orders
- Review position limits

---

### Book Imbalance

**Definition:** `(bid_volume - ask_volume) / (bid_volume + ask_volume)`

**Raw metrics:** `exchange_bid_volume`, `exchange_ask_volume`

| Range | Status | Interpretation |
|-------|--------|----------------|
| -0.2 to +0.2 | Healthy | Balanced order flow |
| -0.3 to -0.2 or +0.2 to +0.3 | Warning | Moderate directional pressure |
| < -0.3 | Critical | Strong sell pressure, potential crash |
| > +0.3 | Critical | Strong buy pressure, potential squeeze |

**Mitigations:**
- Investigate large one-sided positions
- Consider temporary trading halts
- Review for coordinated manipulation

---

## 2. Activity Indicators

### Trade Rate

**Definition:** Trades per minute (computed externally)

**Raw metrics:** `exchange_trades_total` (use `rate()` in Prometheus)

| Range | Status | Interpretation |
|-------|--------|----------------|
| 0.1 - 10/min | Healthy | Active trading |
| < 0.1/min | Warning | Stale market, low interest |
| > 50/min | Warning | Unusually high activity, review for issues |

**Mitigations:**
- Low activity → Add more trading agents, marketing
- High activity → Check for wash trading, system issues

---

### Volume Turnover Rate

**Definition:** `rate(volume) / float_shares` over time period

**Raw metrics:** `exchange_trade_volume_total`, `exchange_float_shares`

| Range (per hour) | Status | Interpretation |
|------------------|--------|----------------|
| 0.5% - 5% | Healthy | Normal turnover |
| < 0.5% | Warning | Low liquidity, stagnant |
| > 10% | Warning | Excessive churn, review strategies |

**Mitigations:**
- Low turnover → Adjust bot strategies, add participants
- High turnover → Check for circular trading

---

### Unique Active Traders

**Definition:** Distinct accounts with trades in time window

**Raw metrics:** Derived from trade events (needs custom tracking)

| Range | Status | Interpretation |
|-------|--------|----------------|
| ≥ 4 | Healthy | Competitive market |
| 2-3 | Warning | Limited competition |
| 1 | Critical | Monopoly risk, no price discovery |

**Mitigations:**
- Onboard more participants
- Review barriers to entry
- Add bot diversity

---

## 3. Price Stability Indicators

### Volatility

**Definition:** Standard deviation of trade prices / mean price × 100

**Raw metrics:** `exchange_last_price` (compute std dev externally)

| Range (per hour) | Status | Interpretation |
|------------------|--------|----------------|
| 0.5% - 5% | Healthy | Normal price discovery |
| < 0.5% | Warning | No price movement, stale |
| 5% - 10% | Warning | Elevated volatility |
| > 10% | Critical | Unstable, potential manipulation |

**Mitigations:**
- Low volatility → Adjust bot strategies, add randomness
- High volatility → Circuit breakers, position limits

---

### Price vs IPO

**Definition:** `(last_price - ipo_price) / ipo_price × 100`

**Raw metrics:** `exchange_last_price`, `exchange_ipo_price`

| Range | Status | Interpretation |
|-------|--------|----------------|
| -30% to +100% | Healthy | Normal price evolution |
| -50% to -30% | Warning | Significant decline |
| < -50% | Critical | Distressed asset |
| +100% to +200% | Warning | Rapid appreciation |
| > +200% | Critical | Potential bubble |

**Mitigations:**
- Distressed → Review fundamentals, consider delisting
- Bubble → Warning announcements, margin requirements

---

## 4. Market Integrity Indicators

### Order Fill Rate

**Definition:** `filled_orders / total_orders × 100`

**Raw metrics:** `exchange_orders_filled_total`, `exchange_orders_total`

| Range | Status | Interpretation |
|-------|--------|----------------|
| 30% - 70% | Healthy | Normal fill rates |
| < 30% | Warning | Orders too aggressive or market broken |
| > 80% | Warning | Orders too passive, check pricing |

**Mitigations:**
- Low fill rate → Review order pricing, market spread
- High fill rate → Verify competitive pricing

---

### Cancel Rate

**Definition:** `cancelled_orders / total_orders × 100`

**Raw metrics:** `exchange_orders_cancelled_total`, `exchange_orders_total`

| Range | Status | Interpretation |
|-------|--------|----------------|
| 10% - 30% | Healthy | Normal strategy adjustment |
| < 10% | Info | Strategies not adjusting (unusual) |
| 30% - 50% | Warning | High cancellation activity |
| > 50% | Critical | Potential quote stuffing |

**Mitigations:**
- High cancel rate → Cancel fees, minimum order lifetime
- Review accounts with excessive cancels

---

### Volume Concentration

**Definition:** Top trader's % of total volume

**Raw metrics:** Derived from trade events per account

| Range | Status | Interpretation |
|-------|--------|----------------|
| < 30% | Healthy | Distributed activity |
| 30% - 50% | Warning | Moderate concentration |
| > 50% | Critical | Single actor dominance |

**Mitigations:**
- Position limits per account
- Encourage new participants
- Review for manipulation

---

## Prometheus Query Examples

```promql
# Spread percentage
(exchange_best_ask - exchange_best_bid) /
((exchange_best_ask + exchange_best_bid) / 2) * 100

# Trade rate per minute
rate(exchange_trades_total[1m]) * 60

# Volume turnover per hour
rate(exchange_trade_volume_total[1h]) / exchange_float_shares * 100

# Book imbalance
(exchange_bid_volume - exchange_ask_volume) /
(exchange_bid_volume + exchange_ask_volume)

# Price vs IPO
(exchange_last_price - exchange_ipo_price) / exchange_ipo_price * 100

# Cancel rate
rate(exchange_orders_cancelled_total[5m]) / rate(exchange_orders_total[5m]) * 100
```

---

## Alert Examples (Alertmanager)

```yaml
groups:
  - name: market_health
    rules:
      - alert: WideSpread
        expr: (exchange_best_ask - exchange_best_bid) / ((exchange_best_ask + exchange_best_bid) / 2) * 100 > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Wide spread on {{ $labels.ticker }}"

      - alert: LowActivity
        expr: rate(exchange_trades_total[10m]) * 60 < 0.1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low trading activity on {{ $labels.ticker }}"

      - alert: HighVolatility
        expr: stddev_over_time(exchange_last_price[1h]) / avg_over_time(exchange_last_price[1h]) * 100 > 10
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High volatility on {{ $labels.ticker }}"
```
