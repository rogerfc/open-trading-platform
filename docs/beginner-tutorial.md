# Beginner Investor Tutorial

Welcome to your first stock trading experience! This tutorial will guide you through buying and selling stocks using the StockExchange simulation platform.

## What You'll Learn

By the end of this tutorial, you will:

- Understand basic stock trading concepts
- Create a trading account with virtual money
- Buy and sell stocks using the command line
- Track your portfolio and see if you're making money
- Visualize your investments on a dashboard

## What is Stock Trading?

**Stocks** are small pieces of ownership in a company. When you buy a stock, you own a tiny part of that company. If the company does well, the stock price usually goes up, and you can sell it for more than you paid - that's called **profit**!

This platform simulates a real stock exchange where:
- Companies have stocks you can buy
- Prices change based on supply and demand
- Automated "agents" trade alongside you, making the market feel alive

---

## Prerequisites

Before starting, make sure these services are running:

| Service | Purpose | Default URL |
|---------|---------|-------------|
| Exchange | Handles all trading | http://localhost:8000 |
| Agent Platform | Runs automated traders | http://localhost:8001 |
| Grafana | Shows pretty charts | http://localhost:3000 |

### Check Everything is Working

Run this command to verify the services are online:

```bash
python -m market.cli status
```

You should see output like this:

```
Configuration
----------------------------------------
Config file: /path/to/.market.yaml

Service Status
----------------------------------------
Exchange (http://localhost:8000): OK
Agent Platform (http://localhost:8001): OK
Grafana (http://localhost:3000): OK
```

> **Tip:** If any service shows "UNREACHABLE", make sure you've started all the services with Docker or manually.

---

## Step 1: Load Your First Market

A **scenario** sets up the market with companies, accounts, and automated traders. Let's start with the basic market.

### See Available Scenarios

```bash
python -m market.cli scenario list
```

Output:
```
Available scenarios:
------------------------------------------------------------
  basic_market.yaml         Basic Market          Minimal scenario with 2 compa...
```

### Load the Basic Market Scenario

This command creates companies and automated traders:

```bash
python -m market.cli scenario load scenario/scenarios/basic_market.yaml -y
```

The `-y` flag skips the confirmation prompt.

You'll see:
```
Loading scenario: Basic Market
  Minimal scenario with 2 companies, 2 accounts, and 1 random trader

Resetting databases...
  Exchange reset
  Agent platform reset

Creating 2 companies...
  Created TECH: TechCorp Industries
  Created BANK: First National Bank

Creating 2 accounts...
  Created alice ($50,000.00)
  Created bob ($50,000.00)

Creating 1 agents...
  Created Alice Random Trader (a1b2c3d4...)

==================================================
Scenario loaded!
```

### What Just Happened?

The scenario created:
- **2 Companies**: TECH (TechCorp Industries) and BANK (First National Bank)
- **2 Accounts**: alice and bob, each with $50,000
- **1 Agent**: "Alice Random Trader" - an automated program that will buy and sell stocks

### Verify the Market is Alive

```bash
python -m market.cli scenario status
```

This shows the loaded scenario and agent status.

---

## Step 2: Exploring the Market

Before buying stocks, let's see what's available.

### View All Companies

```bash
python -m market.cli company list
```

Output:
```
Ticker   Name                           Total Shares     Float
TECH     TechCorp Industries               1,000,000     1,000
BANK     First National Bank                 500,000       500
```

**What do these numbers mean?**
- **Ticker**: The short code for the company (like TECH or BANK)
- **Total Shares**: All shares that exist for this company
- **Float**: Shares available for trading (the rest are locked up)

### Check the Order Book

The **order book** shows what prices people are willing to buy and sell at:

```bash
python -m market.cli orderbook show TECH
```

Output:
```
Order Book: TECH
Spread: 2.00

Bids:
       Price     Quantity
       98.00          100
       97.50           50

Asks:
       Price     Quantity
      100.00          100
      101.00           50
```

**Understanding the Order Book:**
- **Bids** = People wanting to BUY (they're offering these prices)
- **Asks** = People wanting to SELL (they're asking for these prices)
- **Spread** = The gap between highest bid and lowest ask

> **Tip:** The lowest ask price is usually what you'll pay when buying.

### View Recent Trades

See what trades have happened:

```bash
python -m market.cli trade list TECH --limit 5
```

This shows the 5 most recent trades for TECH stock.

---

## Step 3: Create Your Trading Account

Now let's create YOUR account so you can start trading!

### Create an Account with Starting Cash

```bash
python -m market.cli account create student --cash 5000
```

Output:
```
Created account student

API Key (save this!): sk_student_abc123xyz789...
Cash Balance: $5,000.00
```

> **IMPORTANT:** Copy and save your API key! You'll need it for every trade. The API key proves you own this account.

For this tutorial, we'll use this placeholder. Replace it with your actual key:
```
YOUR_API_KEY=sk_student_abc123xyz789
```

### View Your Empty Portfolio

```bash
python -m market.cli portfolio show --api-key YOUR_API_KEY
```

Output:
```
==================================================
  MY PORTFOLIO SUMMARY
==================================================

  Total Portfolio Value: $5,000.00

  Cash Balance:    $   5,000.00
  Holdings Value:  $       0.00

  Cost Basis:      $       0.00
  Unrealized P/L:  $0.00 (0.0%)

  Status: Breaking Even

==================================================
```

You have $5,000 in cash and no stocks yet. Let's change that!

---

## Step 4: Your First Trade - Buying Stock

Time to buy your first stock!

### Place a Market Order

A **python -m market.cli order** buys immediately at the best available price:

```bash
python -m market.cli order create --api-key YOUR_API_KEY --ticker TECH --side BUY --type MARKET --quantity 10
```

**Breaking down this command:**
- `--api-key` = Your account's secret key
- `--ticker TECH` = Buy TechCorp stock
- `--side BUY` = We're buying, not selling
- `--type MARKET` = Buy right now at current price
- `--quantity 10` = Buy 10 shares

Output:
```
Order placed: a1b2c3d4-5678-90ab-cdef-1234567890ab
Order ID          a1b2c3d4-5678-90ab-cdef-1234567890ab
Ticker            TECH
Side              BUY
Type              MARKET
Quantity          10
Price             None
Status            FILLED
```

The status "FILLED" means your order completed successfully!

### Check Your Orders

See all your orders:

```bash
python -m market.cli order list --api-key YOUR_API_KEY
```

### View Your New Holdings

Now let's see what you own:

```bash
python -m market.cli portfolio holdings --api-key YOUR_API_KEY
```

Output:
```
======================================================================
  MY STOCK HOLDINGS
======================================================================

  Stock       Qty   Avg Cost    Current        Value            P/L
  ----------------------------------------------------------------------
  TECH         10     $100.00    $100.50   $  1,005.00       +$5.00

  ----------------------------------------------------------------------
  TOTAL                                    $  1,005.00       +$5.00

======================================================================
```

You now own 10 shares of TECH!

---

## Step 5: Understanding Your Portfolio

Let's look at your full portfolio status:

```bash
python -m market.cli portfolio show --api-key YOUR_API_KEY
```

Output:
```
==================================================
  MY PORTFOLIO SUMMARY
==================================================

  Total Portfolio Value: $5,005.00

  Cash Balance:    $   4,000.00
  Holdings Value:  $   1,005.00

  Cost Basis:      $   1,000.00
  Unrealized P/L:  +$5.00 (+0.5%)

  Status: Making Money!

==================================================
```

**What these numbers mean:**

| Term | Meaning | Your Value |
|------|---------|------------|
| Total Portfolio Value | Everything you own (cash + stocks) | $5,005 |
| Cash Balance | Money available to buy more stocks | $4,000 |
| Holdings Value | Current worth of your stocks | $1,005 |
| Cost Basis | What you paid for your stocks | $1,000 |
| Unrealized P/L | Profit/Loss if you sold now | +$5 |

### Watch Prices Change

Start the trading agents to make the market move:

```bash
python -m market.cli run
```

Wait a few seconds, then check your portfolio again:

```bash
python -m market.cli portfolio show --api-key YOUR_API_KEY
```

The prices might have changed! That's the market in action.

---

## Step 6: Selling Stock

Let's sell some of your shares to lock in profits (or cut losses).

### Place a Limit Sell Order

A **limit order** only executes at your specified price or better:

```bash
python -m market.cli order create --api-key YOUR_API_KEY --ticker TECH --side SELL --type LIMIT --quantity 5 --price 105
```

This says: "Sell 5 shares of TECH, but only if someone will pay at least $105 per share."

### Check Order Status

```bash
python -m market.cli order list --api-key YOUR_API_KEY
```

Your order might show:
- **OPEN** = Waiting for a buyer at your price
- **FILLED** = Sold successfully
- **PARTIAL** = Some shares sold, waiting on the rest

### View Updated Portfolio

After your sell order fills:

```bash
python -m market.cli portfolio holdings --api-key YOUR_API_KEY
```

You should now have fewer shares.

---

## Step 7: Visualizing with Dashboards

Numbers are great, but charts are better! Let's deploy the visual dashboard.

### Deploy Dashboards to Grafana

```bash
python -m market.cli grafana deploy -d portfolio
```

Output:
```
Deployed: portfolio
  URL: http://localhost:3000/d/my-portfolio/my-portfolio
```

### Open Grafana

1. Open your browser to **http://localhost:3000**
2. Default login: admin / admin (if prompted)
3. Navigate to Dashboards → "My Portfolio"

### What You'll See

The **My Portfolio** dashboard shows:

| Panel | What It Shows |
|-------|---------------|
| Total Portfolio Value | Your total wealth (cash + stocks) |
| Profit/Loss | Whether you're making or losing money (color-coded!) |
| Your Returns gauge | Quick visual: green = good, red = bad |
| Portfolio Breakdown | Pie chart of your holdings |
| Value History | Graph of your portfolio over time |
| Investment Glossary | Helpful terms for beginners |

> **Tip:** The dashboard refreshes every 10 seconds, so you can watch your portfolio change in real-time!

---

## Step 8: Stopping the Simulation

When you're done trading:

```bash
python -m market.cli stop
```

This stops all automated trading agents.

**What happens to your positions?** They stay exactly as they are. The market just becomes quiet until you start the agents again.

---

## Key Terms Glossary

| Term | Simple Explanation |
|------|-------------------|
| **Stock/Share** | A tiny piece of ownership in a company |
| **Ticker** | Short code for a company (e.g., TECH, BANK) |
| **Portfolio** | All your investments combined |
| **Bid** | Price someone is willing to pay to buy |
| **Ask** | Price someone wants to sell at |
| **Spread** | Gap between bid and ask prices |
| **Market Order** | Buy/sell immediately at current price |
| **Limit Order** | Buy/sell only at your specified price |
| **Cost Basis** | What you originally paid for stocks |
| **Unrealized P/L** | Profit/loss if you sold everything now |
| **Realized P/L** | Actual profit/loss after you sell |
| **Float** | Shares available for public trading |

---

## Next Steps

Now that you know the basics, try these:

### 1. Experiment with Different Orders

Try buying BANK stock, or place limit orders at specific prices.

### 2. Load a More Complex Scenario

The `market_makers` scenario has more traders and more action:

```bash
python -m market.cli scenario list
python -m market.cli scenario load scenario/scenarios/market_makers.yaml -y
```

### 3. Create Your Own Trading Agent

Automated traders (agents) follow strategies you define. Check out the agent documentation to create your own!

### 4. Explore the Exchange Dashboard

Deploy the exchange dashboard to see the whole market:

```bash
python -m market.cli grafana deploy -d exchange
```

---

## Quick Reference

```bash
# Check services
python -m market.cli status

# Load a scenario
python -m market.cli scenario load scenario/scenarios/basic_market.yaml -y

# Start/stop trading
python -m market.cli run
python -m market.cli stop

# View market
python -m market.cli company list
python -m market.cli orderbook show TECH
python -m market.cli trade list TECH --limit 10

# Your account
python -m market.cli account create myname --cash 10000
python -m market.cli portfolio show --api-key YOUR_KEY
python -m market.cli portfolio holdings --api-key YOUR_KEY

# Trading
python -m market.cli order create --api-key KEY --ticker TECH --side BUY --type MARKET --quantity 10
python -m market.cli order create --api-key KEY --ticker TECH --side SELL --type LIMIT --quantity 5 --price 105
python -m market.cli order list --api-key KEY

# Dashboards
python -m market.cli grafana deploy -d portfolio
python -m market.cli grafana deploy -d exchange
```

---

Happy Trading! Remember: in this simulation, there's no real money at stake, so experiment freely and learn from your mistakes.
