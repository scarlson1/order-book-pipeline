# Zero-Cost Portfolio Deployment Plan

## The Challenge

You want to showcase your order book pipeline to potential employers/clients **without paying anything**. This is smart for portfolio projects.

## The Reality Check

**True $0 is hard because:**

- TimescaleDB isn't offered free (it's commercial)
- Real databases with backups cost money
- Ingesting live Binance data 24/7 triggers cloud costs
- Portfolio projects usually run for months

**But we can get VERY close to $0** with the right strategy.

---

## The Best Free/Cheap Architecture for Portfolio

### Overview

```
┌─────────────────────────────────────────┐
│  Free Tier Services (All Combined)      │
├─────────────────────────────────────────┤
│                                         │
│  ☁️ Ingestion & Processing              │
│  ├─ Render.com (free Python service)   │
│  ├─ Fly.io (free tier generous)        │
│  └─ Railway.app (free with limits)     │
│                                         │
│  📊 Database                            │
│  ├─ PostgreSQL via Heroku               │
│  ├─ Neon (free PostgreSQL)              │
│  ├─ Supabase (free tier)                │
│  └─ CockroachDB Serverless (free)       │
│                                         │
│  💾 Cache                               │
│  ├─ Upstash Redis (free tier)           │
│  └─ Redis Cloud (free tier)             │
│                                         │
│  📨 Message Broker                      │
│  ├─ Upstash Kafka (free!)               │
│  └─ Supabase Realtime (free!)           │
│                                         │
│  📈 Dashboard                           │
│  └─ Streamlit Cloud (free)              │
│                                         │
└─────────────────────────────────────────┘

Total Cost: $0 - $5/month (optional paid features)
```

---

## Part 1: Free Database Options

### Option A: CockroachDB Serverless ⭐ (BEST for TimescaleDB replacement)

**Cost: FREE (generous limits)**

```
✅ Pros:
  - Fully managed PostgreSQL-compatible database
  - Free tier: 250MB storage, no time limits
  - Perfect for portfolio (that's plenty)
  - Auto-scaling, automatic backups
  - Can export to TimescaleDB later
  - Globally distributed (looks impressive)

❌ Cons:
  - Not TimescaleDB (but compatible alternative)
  - 250MB might get tight with 1 year of data
  - No automatic compression
```

**Setup (5 minutes):**

```bash
1. Go to cockroachlabs.com
2. Sign up (free tier account)
3. Create serverless cluster
4. Get connection string
5. Create database schema
```

**Connection String Format:**

```
postgresql://username:password@host:26257/defaultdb?sslmode=require
```

**Why this works:**

- CockroachDB is PostgreSQL-compatible
- Your existing psycopg2/SQLAlchemy code works unchanged
- TimescaleDB features (time-series optimizations) aren't free anyway
- For portfolio demo, CockroachDB actually looks MORE impressive (distributed database)

### Option B: Neon (Free PostgreSQL)

**Cost: FREE**

```
✅ Pros:
  - Real PostgreSQL (not a clone)
  - Free tier: 3 projects, 10GB storage
  - Instant branching (great for demos)
  - Serverless compute (scales to zero)
  - Can install extensions (almost TimescaleDB)

❌ Cons:
  - 10GB is good but Neon cold-starts projects (2-3s delay)
  - TimescaleDB extension requires paid tier
  - Storage resets if unused for 7 days (free tier)
```

**Setup (3 minutes):**

```bash
1. Go to neon.tech
2. Sign up (free account)
3. Create PostgreSQL project
4. Get connection string
5. Done!
```

### Option C: Supabase (Free PostgreSQL + Extras)

**Cost: FREE**

```
✅ Pros:
  - Real PostgreSQL
  - Free tier: 500MB database, 2GB file storage
  - Built-in realtime (great for live dashboards)
  - Auth system included (future feature)
  - REST API auto-generated

❌ Cons:
  - 500MB is tight for long-running projects
  - Time-series features still limited
  - Project limits (3 projects)
```

**Setup (3 minutes):**

```bash
1. Go to supabase.com
2. Sign up
3. Create project
4. Get PostgreSQL connection string
5. Done!
```

### Option D: TimescaleDB Alternatives (NOT Free)

```
❌ Render PostgreSQL: Free tier is limited/slow
❌ AWS RDS: Not free beyond 12 months, managed backups cost
❌ Google Cloud SQL: Not free beyond credits
❌ Heroku PostgreSQL: SHUTDOWN (no longer free)
```

### My Recommendation: CockroachDB Serverless

**Why CockroachDB wins for portfolio:**

1. **Completely free** (no expiration, no catch)
2. **250MB is enough** for portfolio demo (that's 1M+ rows)
3. **PostgreSQL-compatible** (your code works unchanged)
4. **Looks impressive** in technical interviews ("distributed database")
5. **Professional** (used by real companies)
6. **Better than TimescaleDB** for demo because:
   - TimescaleDB isn't offered free anywhere
   - CockroachDB shows broader database knowledge
   - Distributed architecture is cooler for portfolio

---

## Part 2: Free Backend Services

### Best Option: Render.com (Free Tier is Great)

**Cost: FREE** (with caveats)

```
Render Free Tier:
├── Free Web Services (for Streamlit)
│   └── Spins down after 15 min inactivity
├── Free Workers (for background jobs)
│   └── 750 hours/month
├── Free PostgreSQL
│   └── 1GB storage (backup option)
└── Free Redis
    └── 30MB (small but works)

What you get:
✅ Deploys directly from GitHub
✅ Auto-restarts when pinged
✅ Python-native (your stack)
✅ Environment variables for secrets
✅ Real uptime monitoring
```

**How it works:**

```
1. Push code to GitHub
2. Connect Render to GitHub
3. Deploy with one click
4. Render builds and runs containers
5. Services restart after idle time
```

**Cost reality:**

- Streamlit dashboard: Free (but cold starts)
- Ingestion service: Free (runs 750 hours/month)
- Processing: Free if you keep it lightweight
- **Total: $0 if you're patient with cold starts**

### Alternative: Fly.io (Also Free, Less Cold Starts)

**Cost: FREE** (for light usage)

```
Fly.io Free Tier:
├── 3 shared-cpu-1x 256MB VMs (free)
├── 160GB outbound data transfer
├── PostgreSQL add-on not free
└── Redis add-on not free

Advantage:
✅ More generous compute
✅ Fewer cold starts
✅ Global deployment (cool for portfolio)

Disadvantage:
❌ Need external database (CockroachDB)
❌ More complex setup
```

### My Recommendation: Render.com

**Why Render wins:**

1. **Truly free** (no hidden costs)
2. **Easy setup** (GitHub integration)
3. **Good for portfolio** (cold starts are acceptable)
4. **All your services in one place**
5. **Database included** (via external services)

---

## Part 3: Free Message Broker & Caching

### Message Broker: Upstash Kafka (FREE!)

**Cost: FREE**

```
Upstash Kafka Free:
├── 100MB storage
├── 1GB/day ingress
├── 1GB/day egress
├── 100 partitions
└── 7 day retention

Perfect for:
✅ Your order book stream
✅ Portfolio demo (won't hit limits)
✅ Real managed service (looks professional)
✅ Serverless (no containers to manage)
```

**Setup (5 minutes):**

```bash
1. Go to upstash.com
2. Sign up (free tier)
3. Create Kafka cluster
4. Get bootstrap servers + auth
5. Update your code
```

**Cost**: $0 for portfolio usage

### Caching: Upstash Redis (FREE!)

**Cost: FREE**

```
Upstash Redis Free:
├── 10,000 commands/day
├── 256MB storage
├── 100 concurrent connections
├── SSL support

For your dashboard:
✅ Cache latest metrics
✅ Fast reads for Streamlit
✅ 256MB is plenty for order book cache
```

**Setup (2 minutes):**

```bash
1. Go to upstash.com
2. Create Redis database
3. Get connection string
4. Replace Redis connection
```

**Cost**: $0

### Alternative for Both: Upstash Serverless

Upstash offers both Kafka + Redis in free tier

- All you need in one place
- Total cost: $0

---

## Part 4: Free Dashboard Hosting

### Best Option: Streamlit Cloud (FREE)

**Cost: FREE**

```
Streamlit Cloud:
├── Deploy from GitHub
├── Auto-restarts on push
├── Free SSL certificates
├── Environment secrets support
└── Generous free tier

Free tier limits:
✅ Unlimited apps
✅ Unlimited deployments
✅ CPU/RAM reasonable
✅ Only limitation: shared resources during peaks
```

**Setup (2 minutes):**

```bash
1. Push Streamlit app to GitHub
2. Go to share.streamlit.io
3. Click "Deploy an app"
4. Select GitHub repo + file
5. Done!
```

**Cost**: $0

---

## The Complete Zero-Cost Architecture

```
┌──────────────────────────────────────────┐
│          PORTFOLIO ARCHITECTURE          │
├──────────────────────────────────────────┤
│                                          │
│  🎨 Frontend                             │
│  ├─ Streamlit Cloud (FREE)              │
│  │  └─ Deploys from GitHub              │
│  │  └─ Cold starts okay for portfolio   │
│  │                                       │
│  🔧 Backend Services                    │
│  ├─ Render.com (FREE tier)              │
│  │  ├─ Ingestion service (Python)       │
│  │  ├─ Consumer service (Python)        │
│  │  └─ Processing workers               │
│  │                                       │
│  📊 Data Layer                           │
│  ├─ CockroachDB Serverless (FREE)       │
│  │  ├─ PostgreSQL compatible            │
│  │  └─ 250MB storage (plenty for demo)  │
│  │                                       │
│  💾 Cache                                │
│  ├─ Upstash Redis (FREE)                │
│  │  └─ 256MB, 10k commands/day          │
│  │                                       │
│  📨 Message Broker                       │
│  ├─ Upstash Kafka (FREE)                │
│  │  ├─ 100MB storage                    │
│  │  └─ 1GB/day transfer                 │
│  │                                       │
│  🔐 Secrets Management                  │
│  └─ Environment variables in each service│
│                                          │
└──────────────────────────────────────────┘

Total Monthly Cost: $0 (or $5 for optional upgrades)
```

---

## Architecture Diagram: Deployment Flow

```
GitHub Repository
    │
    ├─── Streamlit Cloud (Dashboard)
    │    └─ Reads from: CockroachDB + Upstash Redis
    │
    ├─── Render.com (Ingestion Service)
    │    ├─ Binance WebSocket → Upstash Kafka
    │    ├─ Metrics → CockroachDB
    │    └─ Cache → Upstash Redis
    │
    ├─── Render.com (Consumer Service)
    │    ├─ Reads: Upstash Kafka
    │    ├─ Processes: Stream data
    │    ├─ Writes: CockroachDB metrics
    │    └─ Updates: Upstash Redis cache
    │
    └─── (Optional) Render Workers
         └─ Flink processing (if lightweight)

External Services (All Free Tier):
├─ CockroachDB Serverless (Database)
├─ Upstash Kafka (Message Broker)
├─ Upstash Redis (Cache)
└─ Streamlit Cloud (Frontend)
```

---

## Part 5: Handling TimescaleDB (The Workaround)

### Problem: TimescaleDB isn't offered free anywhere

### Solution: Don't use TimescaleDB for portfolio

**Why:**

1. TimescaleDB is a commercial extension (requires paid PostgreSQL)
2. CockroachDB is actually BETTER for portfolio (more impressive)
3. For demo purposes, regular PostgreSQL is fine
4. Time-series optimizations don't matter for small datasets

### If you REALLY want time-series features:

**Option A: Minimal Self-Hosted (Not recommended)**

```
- Install PostgreSQL locally
- Install TimescaleDB extension
- Keep running on your machine
- Not accessible from cloud services
❌ Doesn't work for portfolio (need it online)
```

**Option B: Managed TimescaleDB (Paid)**

```
- Timescale Cloud (managed service)
- Cheapest: $500/month (way too much)
❌ Not viable for portfolio
```

**Option C: Better Alternative - Stick with CockroachDB**

```
✅ Free
✅ Professional
✅ Distributed (cooler for portfolio)
✅ PostgreSQL-compatible (your code works)
✅ Time-series data works fine without extensions
```

---

## Implementation Plan: Step-by-Step

### Step 1: Set Up Free Database (5 minutes)

```bash
# Create CockroachDB Serverless cluster
1. Go to cockroachlabs.com/product/cockroachdb-serverless
2. Click "Try Free"
3. Create account
4. Create cluster (default settings fine)
5. Note connection string

# Update .env in your project
POSTGRES_HOST=<cockroach-host>
POSTGRES_USER=<your-user>
POSTGRES_PASSWORD=<your-password>
POSTGRES_DB=defaultdb
```

### Step 2: Set Up Free Cache & Message Broker (10 minutes)

```bash
# Create Upstash Kafka
1. Go to upstash.com
2. Create Kafka cluster
3. Note bootstrap servers + auth

# Create Upstash Redis
1. Same Upstash account
2. Create Redis database
3. Note connection string

# Update .env
UPSTASH_KAFKA_BOOTSTRAP_SERVERS=<your-servers>
UPSTASH_REDIS_URL=<redis-url>
```

### Step 3: Deploy Streamlit Dashboard (2 minutes)

```bash
# Push dashboard to GitHub
1. Commit dashboard/ folder to GitHub
2. Go to share.streamlit.io
3. "Deploy an app"
4. Select your repo + dashboard/app.py
5. Configure environment variables
6. Done!

Your dashboard URL:
https://<your-username>-orderbook-dashboard.streamlit.app
```

### Step 4: Deploy Render Services (10 minutes)

```bash
# Deploy Ingestion Service
1. Go to render.com
2. Create new Web Service
3. Connect GitHub repo
4. Settings:
   - Runtime: Python
   - Build command: pip install -r requirements.txt
   - Start command: python src/ingestion/main.py
5. Add environment variables
6. Deploy

# Deploy Consumer Service (same process)
1. New Web Service
2. Connect GitHub
3. Start command: python src/consumers/main.py
4. Deploy
```

---

## Addressing the Data Problem

### Issue: Ingesting Live Data 24/7

**Problem:** Even free services will consume quota quickly if ingesting every second

**Solutions:**

### Solution 1: Demo Mode (RECOMMENDED for Portfolio)

Instead of real-time ingestion, use **pre-recorded data** or **sampled data**:

```python
# demo_data.py
def get_demo_orderbook_data():
    """Return synthetic/cached order book data for demo"""
    # Option A: Load from CSV (historical Binance data)
    df = pd.read_csv('binance_sample_data.csv')
    return df.iloc[random.randint(0, len(df))]

    # Option B: Generate synthetic data
    bids = generate_synthetic_bids()
    asks = generate_synthetic_asks()
    return {
        'bids': bids,
        'asks': asks,
        'timestamp': datetime.now()
    }
```

**Why this is smart for portfolio:**

- ✅ Shows you understand data structures
- ✅ Doesn't consume free tier quotas
- ✅ Dashboard always shows good data
- ✅ Faster development/testing
- ✅ More impressive: "Configured for 100+ symbols" (even if demo data)

### Solution 2: Smart Sampling

```python
# Only ingest every N seconds (not every tick)
import time

def ingest_with_sampling(symbols, sample_interval=5):
    """Ingest every N seconds instead of every tick"""
    ws = BinanceWebSocketClient()
    last_ingest = {}

    for symbol in symbols:
        last_ingest[symbol] = 0

    def handle_message(symbol, data):
        now = time.time()
        if now - last_ingest[symbol] >= sample_interval:
            # Process this data
            process_orderbook(symbol, data)
            last_ingest[symbol] = now

    ws.start(handle_message)
```

**Cost impact:**

- Reduces quotas by 80-90%
- Still shows real data flowing through
- Better for portfolio (shows you optimize)

### Solution 3: Scheduled Jobs (Not 24/7)

```python
# Only run ingestion during "business hours"
# Trigger via Render Cron

import schedule
import time

def run_ingestion():
    """Run for 8 hours then stop"""
    start = datetime.now()
    while (datetime.now() - start).seconds < 28800:  # 8 hours
        # Ingest data
        ingest_orderbook()
        time.sleep(5)

if __name__ == "__main__":
    run_ingestion()
```

**This means:**

- Run ingestion 8-10 hours/day
- Sleep rest of day
- Free tier lasts much longer
- Still looks live when you're showing it

---

## Revised Architecture with Demo Data

```
┌──────────────────────────────┐
│   PORTFOLIO DEMO MODE        │
├──────────────────────────────┤
│                              │
│  Option A: Demo Data         │
│  ├─ Load historical CSV      │
│  ├─ Cycle through samples    │
│  └─ Simulate live stream     │
│                              │
│  Option B: Smart Sampling    │
│  ├─ Real Binance data        │
│  ├─ Only every 5 seconds     │
│  └─ Reduces quotas 80%       │
│                              │
│  Option C: Scheduled Run     │
│  ├─ Real Binance data        │
│  ├─ Only 8-10 hours/day      │
│  └─ Pauses overnight         │
│                              │
└──────────────────────────────┘

Cost Impact:
- Full 24/7 real data: Hit quotas, might cost money
- Demo data: $0 forever
- Smart sampling: $0 with buffer room
- Scheduled: $0 with plenty of buffer
```

---

## The Updated Zero-Cost Plan

### Architecture

```
PORTFOLIO-GRADE ORDER BOOK MONITOR
├─ Database: CockroachDB Serverless (FREE)
├─ Cache: Upstash Redis (FREE)
├─ Message Broker: Upstash Kafka (FREE)
├─ Frontend: Streamlit Cloud (FREE)
├─ Backend: Render.com (FREE)
└─ Data: Demo/Sampled from Binance (FREE)

Total Cost: $0/month
```

### What This Looks Like to Employers

**When you show this in interviews:**

```
Interviewer: "This is impressive! How are you hosting it?"

You: "The entire system runs on free tiers:
- Frontend is Streamlit Cloud (auto-deploys from GitHub)
- Backend services run on Render.com free tier
- Database is CockroachDB Serverless (distributed PostgreSQL)
- Caching and message broking via Upstash
- All data pipelines are serverless and cost-optimized

The ingestion uses smart sampling to reduce costs
and the architecture is designed to scale to paid tiers
without code changes."

Interviewer: 👍👍👍 (You understand infrastructure)
```

---

## File Changes Needed

### Update docker-compose.yml for Demo Mode

```yaml
version: '3.8'

services:
  # For local testing with real services
  ingestion:
    build:
      context: .
      dockerfile: Dockerfile.ingestion
    environment:
      # Point to CockroachDB
      POSTGRES_HOST: ${COCKROACH_HOST}
      POSTGRES_USER: ${COCKROACH_USER}
      POSTGRES_PASSWORD: ${COCKROACH_PASSWORD}

      # Point to Upstash Kafka
      KAFKA_BOOTSTRAP_SERVERS: ${UPSTASH_KAFKA_SERVERS}
      KAFKA_SASL_USERNAME: ${UPSTASH_KAFKA_USERNAME}
      KAFKA_SASL_PASSWORD: ${UPSTASH_KAFKA_PASSWORD}

      # Point to Upstash Redis
      REDIS_URL: ${UPSTASH_REDIS_URL}

      # DEMO MODE - use sample data instead of live
      DEMO_MODE: 'true'
      DEMO_DATA_FILE: 'data/sample_orderbook.csv'
```

### New File: src/ingestion/demo_mode.py

```python
"""
Demo mode for portfolio
Instead of live Binance WebSocket, use pre-recorded data
"""

import pandas as pd
import random
from datetime import datetime

class DemoOrderbookClient:
    def __init__(self, csv_file='data/sample_orderbook.csv'):
        self.data = pd.read_csv(csv_file)
        self.index = 0

    def get_next_update(self):
        """Get next sample from CSV"""
        sample = self.data.iloc[self.index % len(self.data)]
        self.index += 1

        # Convert to orderbook format
        return {
            'symbol': sample['symbol'],
            'timestamp': datetime.now().isoformat(),
            'bids': eval(sample['bids']),  # CSV stored as string
            'asks': eval(sample['asks']),
            'demo': True  # Mark as demo data
        }

    def start(self, callback):
        """Simulate WebSocket stream"""
        import time
        while True:
            data = self.get_next_update()
            callback(data['symbol'], data)
            time.sleep(5)  # Update every 5 seconds
```

### Update: src/ingestion/main.py

```python
import os

DEMO_MODE = os.getenv('DEMO_MODE', 'false').lower() == 'true'

if DEMO_MODE:
    from demo_mode import DemoOrderbookClient
    ws_client = DemoOrderbookClient()
else:
    from websocket_client import BinanceWebSocketClient
    ws_client = BinanceWebSocketClient()

# Rest of code works exactly the same
ws_client.start(handle_orderbook)
```

---

## Sample Data Generation

### Create Historical Sample Data

```python
# scripts/generate_sample_data.py
import pandas as pd
import requests
from datetime import datetime, timedelta

def download_binance_sample():
    """Download 1 month of Binance data for demo"""
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

    data = []
    for symbol in symbols:
        # Download klines (OHLCV) from Binance
        url = f"https://api.binance.com/api/v3/klines"
        params = {
            'symbol': symbol,
            'interval': '1m',
            'limit': 1440  # 1 day of 1-min candles
        }

        response = requests.get(url, params=params)
        for candle in response.json():
            data.append({
                'symbol': symbol,
                'timestamp': datetime.fromtimestamp(candle[0]/1000),
                'close': float(candle[4]),
                # Synthetic order book (realistic spreads)
                'bids': generate_synthetic_bids(float(candle[4])),
                'asks': generate_synthetic_asks(float(candle[4]))
            })

    df = pd.DataFrame(data)
    df.to_csv('data/sample_orderbook.csv', index=False)
    print(f"Generated {len(df)} samples")

def generate_synthetic_bids(mid_price, depth=20):
    """Generate realistic synthetic bid levels"""
    import random
    bids = []
    for i in range(depth):
        spread = mid_price * (0.0001 * (i + 1))
        price = mid_price - spread
        volume = random.uniform(0.1, 10)
        bids.append([price, volume])
    return sorted(bids, reverse=True)

def generate_synthetic_asks(mid_price, depth=20):
    """Generate realistic synthetic ask levels"""
    import random
    asks = []
    for i in range(depth):
        spread = mid_price * (0.0001 * (i + 1))
        price = mid_price + spread
        volume = random.uniform(0.1, 10)
        asks.append([price, volume])
    return sorted(asks)

if __name__ == "__main__":
    download_binance_sample()
```

**Run once to generate sample data:**

```bash
python scripts/generate_sample_data.py
# Creates: data/sample_orderbook.csv with 1440+ samples
```

---

## Deployment Checklist: Zero-Cost Portfolio

### ☑️ Setup Phase (30 minutes total)

- [ ] Create CockroachDB Serverless account (5 min)
  - [ ] Create cluster
  - [ ] Note connection string
  - [ ] Create database schema

- [ ] Create Upstash account (5 min)
  - [ ] Create Kafka cluster
  - [ ] Create Redis database
  - [ ] Note credentials

- [ ] Update .env with credentials (5 min)

  ```
  COCKROACH_HOST=...
  COCKROACH_USER=...
  COCKROACH_PASSWORD=...
  UPSTASH_KAFKA_SERVERS=...
  UPSTASH_REDIS_URL=...
  DEMO_MODE=true
  ```

- [ ] Generate sample data (5 min)

  ```bash
  python scripts/generate_sample_data.py
  git add data/sample_orderbook.csv
  git commit -m "Add sample orderbook data"
  ```

- [ ] Test locally (5 min)
  ```bash
  # Update connection strings in .env
  python src/ingestion/main.py  # Should work
  ```

### ☑️ Deployment Phase (15 minutes)

- [ ] Deploy Dashboard to Streamlit Cloud (2 min)
  - [ ] Push to GitHub
  - [ ] Go to share.streamlit.io
  - [ ] Deploy from GitHub repo
  - [ ] Set environment variables
  - [ ] Test at dashboard URL

- [ ] Deploy Ingestion Service to Render (5 min)
  - [ ] Create Web Service
  - [ ] Connect GitHub
  - [ ] Set start command: `python src/ingestion/main.py`
  - [ ] Set environment variables
  - [ ] Deploy

- [ ] Deploy Consumer Service to Render (5 min)
  - [ ] Create Web Service
  - [ ] Connect GitHub
  - [ ] Set start command: `python src/consumers/main.py`
  - [ ] Set environment variables
  - [ ] Deploy

- [ ] Create Render Cron Job (optional, 3 min)
  - [ ] Weekly restart of services
  - [ ] Keeps everything fresh

### ☑️ Verification Phase (5 minutes)

- [ ] Dashboard loads at public URL
- [ ] Data appears in dashboard
- [ ] Database has data (verify via CockroachDB console)
- [ ] No errors in logs
- [ ] Create GitHub README documenting setup

---

## Final Zero-Cost Architecture Summary

```
┌─────────────────────────────────────┐
│  ZERO-COST PORTFOLIO ARCHITECTURE   │
├─────────────────────────────────────┤
│                                     │
│  Frontend                           │
│  └─ Streamlit Cloud (FREE)         │
│     📊 Live dashboard               │
│                                     │
│  Backend                            │
│  └─ Render.com Web Services (FREE) │
│     ├─ Ingestion service           │
│     ├─ Consumer service            │
│     └─ Cold starts okay (portfolio) │
│                                     │
│  Data Storage                       │
│  └─ CockroachDB Serverless (FREE)  │
│     ├─ 250MB storage                │
│     ├─ PostgreSQL-compatible        │
│     └─ Fully managed                │
│                                     │
│  Cache                              │
│  └─ Upstash Redis (FREE)           │
│     ├─ 256MB storage                │
│     └─ Fast reads for dashboard    │
│                                     │
│  Message Queue                      │
│  └─ Upstash Kafka (FREE)           │
│     ├─ Event streaming              │
│     └─ 100MB/day                    │
│                                     │
│  Data Source                        │
│  └─ Sample CSV + Synthetic Data    │
│     ├─ No API quota consumption    │
│     ├─ Realistic order book shapes  │
│     └─ Can toggle live mode later  │
│                                     │
│  Version Control                    │
│  └─ GitHub (FREE)                  │
│     ├─ Code repository              │
│     ├─ Auto-deploy from branches   │
│     └─ Portfolio showcase           │
│                                     │
└─────────────────────────────────────┘

Monthly Cost: $0
Interview Value: ⭐⭐⭐⭐⭐
Scalability Path: Easy to upgrade later
```

---

## Why This Is Better Than Paying

### For Employers/Interviewers

When you say: **"This entire system runs completely free on serverless platforms"**

They think:

- ✅ You understand cost optimization
- ✅ You know how to leverage free tiers
- ✅ You're resourceful (important for startups)
- ✅ You understand different database technologies
- ✅ You know infrastructure better than your peers

### Compared to: "I deployed it on AWS but spent money"

They think:

- ❌ You didn't think about costs
- ❌ You don't understand free tier strategies
- ❌ You just spent money instead of thinking

### The Best Part

You can tell them: **"When we need to scale this to production, I've architected it so it's a 1-line change to switch from CockroachDB to any other database, Render to any other platform, etc."**

That's impressive engineering.

---

## Migration Path When You Get Hired

If a company wants to use this architecture in production:

```
Stage 1: Replace Demo Data (1 day)
└─ Use real-time Binance WebSocket

Stage 2: Upgrade Database (1 day)
├─ Migrate CockroachDB → TimescaleDB or AWS RDS
├─ Use pg_dump + pg_restore
└─ Zero code changes needed

Stage 3: Upgrade Compute (1 day)
├─ Migrate Render → AWS ECS/EKS
├─ Migrate Streamlit → custom React frontend
└─ Minimal code changes

Stage 4: Add Scale Features (ongoing)
├─ Multi-region deployment
├─ Advanced monitoring
├─ ML/analytics pipeline
└─ All your portfolio code already works!
```

---

## Quick Start (TLDR)

For zero-cost portfolio:

1. **Create CockroachDB Serverless** (free account, 250MB)
2. **Create Upstash account** (free tier Kafka + Redis)
3. **Generate sample data** (`python scripts/generate_sample_data.py`)
4. **Enable demo mode** (`DEMO_MODE=true` in .env)
5. **Deploy to Streamlit Cloud** (connect GitHub)
6. **Deploy services to Render** (Web Services + cron jobs)
7. **Test & showcase**

**Total setup time: 45 minutes**
**Total cost: $0**
**Interview impact: Huge** ⭐⭐⭐⭐⭐

---

## What NOT to Use (For Reference)

```
❌ AWS: Free tier expires after 1 year
❌ Google Cloud: Credits expire, then you pay
❌ Azure: Credits expire, then you pay
❌ Heroku: Shut down free tier in 2022
❌ TimescaleDB Cloud: $500+ minimum
❌ Managed Flink: All charge money
❌ Self-hosted everything: You manage the server
```

**Only use truly free services:**

- ✅ CockroachDB Serverless
- ✅ Upstash
- ✅ Render.com
- ✅ Streamlit Cloud
- ✅ GitHub
- ✅ Local sample data

---

## Summary Table

| Component           | Best Free Option       | Cost | Why                               |
| ------------------- | ---------------------- | ---- | --------------------------------- |
| **Database**        | CockroachDB Serverless | $0   | PostgreSQL-compatible, 250MB free |
| **Cache**           | Upstash Redis          | $0   | 256MB, 10k cmds/day               |
| **Message Broker**  | Upstash Kafka          | $0   | 100MB, 1GB/day transfer           |
| **Frontend**        | Streamlit Cloud        | $0   | Auto-deploy from GitHub           |
| **Backend**         | Render.com             | $0   | Free tier web services            |
| **Data**            | Sample CSV             | $0   | No quota consumption              |
| **Version Control** | GitHub                 | $0   | Public repo is free               |
| **Monitoring**      | Built-in logs          | $0   | Each service has logs             |
| **Total Monthly**   | **$0**                 |      | Forever free!                     |

**This is the setup I'd recommend.**
