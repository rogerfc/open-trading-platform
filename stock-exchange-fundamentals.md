# Stock Exchange Simulation - Learning Fundamentals

## Phase 0: What is a Stock Exchange?

### Core Purpose
A stock exchange is a marketplace where buyers and sellers trade ownership shares (stocks/equities) of companies. It serves as:
- **Price discovery mechanism** - determining fair market value through supply/demand
- **Liquidity provider** - enabling easy buying/selling of shares
- **Regulated environment** - ensuring fair, transparent, and orderly trading

### Key Concepts to Understand

#### 1. What Gets Traded
- **Stocks/Shares** - fractional ownership in a company
- **Price** - current value at which trades occur
- **Volume** - how many shares are traded
- **Market capitalization** - total company value (price × total shares)

#### 2. The Order Book
The order book is the heart of an exchange - a list of all buy and sell orders waiting to be matched.

**Two sides:**
- **Bids** - buy orders (what people will pay)
- **Asks/Offers** - sell orders (what people want to receive)

**Spread** - the gap between highest bid and lowest ask

#### 3. Order Types (Basic)
- **Market order** - buy/sell immediately at best available price
- **Limit order** - buy/sell only at specified price or better
  - Sits in order book until matched or cancelled

#### 4. How Trades Happen
- **Order matching** - exchange pairs buy and sell orders
- **Price-time priority** (most common):
  - Best price gets matched first
  - If same price, earliest order goes first
- A trade occurs when a bid meets or exceeds an ask

#### 5. Market Participants (Actors)
- **Investors** - buy and hold for long term
- **Traders** - buy and sell frequently for short-term profit
- **Market makers** - continuously post buy and sell orders to provide liquidity
- **Companies** - issue shares (IPO), buy back shares
- **Regulators** - enforce rules, prevent manipulation

#### 6. Time Aspects
- **Trading sessions** - when market is open (e.g., 9:30am-4pm)
- **Pre-market/after-hours** - limited trading outside main session
- **Continuous trading** - orders matched as they arrive
- **Call auctions** - orders accumulated then matched at specific times

### Questions to Research Further

Before building, understand:
1. How does price discovery actually work? Why do prices move?
2. What causes the bid-ask spread to widen or narrow?
3. Why do market makers exist? What's their incentive?
4. What prevents market manipulation?
5. How do order books handle large orders that can't be filled at one price?

### Learning Resources to Explore
- Real exchange documentation (NYSE, NASDAQ mechanisms)
- Order book visualizations
- Market microstructure basics
- Simple supply/demand economics

### Next Phase
Once these concepts are clear, move to **Phase 1: Understanding Core Mechanics** (order books, matching algorithms, basic order types in detail).

---

*This document is a living reference. Update as understanding deepens.*
