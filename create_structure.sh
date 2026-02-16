#!/bin/bash

# Script to generate the complete orderbook-monitor project structure
# Run this after extracting the initial files

set -e

echo "=================================================="
echo "Creating Order Book Monitor Directory Structure"
echo "=================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to create directory and print status
create_dir() {
    local dir=$1
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo -e "${GREEN}✓${NC} Created: $dir"
    else
        echo -e "${BLUE}→${NC} Exists:  $dir"
    fi
}

# Function to create file with placeholder content
create_file() {
    local file=$1
    local content=$2
    if [ ! -f "$file" ]; then
        echo "$content" > "$file"
        echo -e "${GREEN}✓${NC} Created: $file"
    else
        echo -e "${BLUE}→${NC} Exists:  $file"
    fi
}

echo "Creating main source directories..."
echo ""

# Source code structure
create_dir "src"
create_dir "src/ingestion"
create_dir "src/common"

# Dashboard structure
create_dir "dashboard"
create_dir "dashboard/components"
create_dir "dashboard/data"
create_dir "dashboard/utils"
create_dir "dashboard/pages"

# Tests structure
create_dir "tests"
create_dir "tests/unit"
create_dir "tests/integration"
create_dir "tests/e2e"
create_dir "tests/fixtures"

# Scripts
create_dir "scripts"

# Documentation
create_dir "docs"
create_dir "docs/images"

# Grafana (already exists from docker-compose setup)
create_dir "grafana/dashboards"
create_dir "grafana/datasources"

# Data directories
create_dir "logs"
create_dir "data/raw"
create_dir "data/processed"
create_dir "data/exports"

# Optional directories
create_dir "notebooks"
create_dir ".vscode"
create_dir ".github/workflows"
create_dir ".github/ISSUE_TEMPLATE"

echo ""
echo "Creating __init__.py files..."
echo ""

# Create __init__.py files
create_file "src/__init__.py" "\"\"\"Order Book Monitor - Real-time order book imbalance monitoring.\"\"\""
create_file "src/ingestion/__init__.py" "\"\"\"Data ingestion service.\"\"\""
create_file "src/common/__init__.py" "\"\"\"Common utilities and shared code.\"\"\""
create_file "dashboard/__init__.py" "\"\"\"Streamlit dashboard application.\"\"\""
create_file "dashboard/components/__init__.py" "\"\"\"Reusable dashboard components.\"\"\""
create_file "dashboard/data/__init__.py" "\"\"\"Data fetching layer.\"\"\""
create_file "dashboard/utils/__init__.py" "\"\"\"Dashboard utilities.\"\"\""
create_file "tests/__init__.py" "\"\"\"Test suite.\"\"\""
create_file "tests/unit/__init__.py" "\"\"\"Unit tests.\"\"\""
create_file "tests/integration/__init__.py" "\"\"\"Integration tests.\"\"\""
create_file "tests/e2e/__init__.py" "\"\"\"End-to-end tests.\"\"\""
create_file "scripts/__init__.py" "\"\"\"Utility scripts.\"\"\""

echo ""
echo "Creating placeholder files..."
echo ""

# Ingestion service files
create_file "src/ingestion/websocket_client.py" "\"\"\"Binance WebSocket client.\"\"\"
# TODO: Implement WebSocket connection to Binance
# - Connect to wss://stream.binance.com:9443/ws
# - Subscribe to depth streams
# - Handle reconnection
"

create_file "src/ingestion/orderbook_parser.py" "\"\"\"Order book data parser.\"\"\"
# TODO: Parse and validate order book data
# - Parse WebSocket messages
# - Validate structure
# - Convert to internal models
"

create_file "src/ingestion/metrics_calculator.py" "\"\"\"Calculate order book imbalance metrics.\"\"\"
# TODO: Implement metric calculations
# - Imbalance ratio
# - Weighted imbalance
# - Spread calculations
# - VTOB ratio
"

create_file "src/ingestion/alert_engine.py" "\"\"\"Alert detection and generation.\"\"\"
# TODO: Implement alert logic
# - Check thresholds
# - Detect imbalance flips
# - Generate alert objects
"

create_file "src/ingestion/data_writer.py" "\"\"\"Write metrics to storage backends.\"\"\"
# TODO: Implement data writers
# - Write to TimescaleDB
# - Cache in Redis
# - Publish to Kafka (optional)
"

# Common utilities
create_file "src/common/database.py" "\"\"\"PostgreSQL/TimescaleDB client.\"\"\"
# TODO: Implement database client
# - Connection pooling
# - Query methods
# - Error handling
"

create_file "src/common/redis_client.py" "\"\"\"Redis client wrapper.\"\"\"
# TODO: Implement Redis client
# - Connection management
# - Get/set operations
# - Key naming conventions
"

create_file "src/common/kafka_client.py" "\"\"\"Kafka producer/consumer (optional).\"\"\"
# TODO: Implement Kafka client
# - Producer for metrics
# - Consumer for processing
"

create_file "src/common/models.py" "\"\"\"Pydantic data models.\"\"\"
from pydantic import BaseModel, Field
from typing import List, Tuple, Optional
from datetime import datetime
from enum import Enum

# TODO: Define all data models
# - OrderBookSnapshot
# - OrderBookMetrics
# - Alert
# - Enums for types and severity
"

# Dashboard components
create_file "dashboard/components/gauge.py" "\"\"\"Imbalance gauge component.\"\"\"
import plotly.graph_objects as go
import streamlit as st

# TODO: Create gauge visualization
# - Plotly indicator gauge
# - Color coding
"

create_file "dashboard/components/timeseries.py" "\"\"\"Time series chart components.\"\"\"
import plotly.graph_objects as go
import streamlit as st

# TODO: Create time series charts
# - Dual-axis plots
# - Zooming and panning
"

create_file "dashboard/components/orderbook_viz.py" "\"\"\"Order book visualization.\"\"\"
import plotly.graph_objects as go
import streamlit as st

# TODO: Create order book depth visualization
# - Stacked area chart
# - Heatmap
"

create_file "dashboard/components/metrics_cards.py" "\"\"\"Metric display cards.\"\"\"
import streamlit as st

# TODO: Create metric cards
# - Current values
# - Delta indicators
"

create_file "dashboard/components/alert_feed.py" "\"\"\"Alert feed component.\"\"\"
import streamlit as st

# TODO: Create alert feed
# - Recent alerts table
# - Filtering
"

create_file "dashboard/data/db_queries.py" "\"\"\"Database query functions.\"\"\"
# TODO: Implement database queries
# - Fetch recent metrics
# - Fetch time series
# - Fetch alerts
"

create_file "dashboard/data/redis_cache.py" "\"\"\"Redis data fetching.\"\"\"
# TODO: Implement Redis queries
# - Fetch cached data
# - Handle cache misses
"

create_file "dashboard/utils/formatting.py" "\"\"\"Data formatting utilities.\"\"\"
# TODO: Formatting helpers
# - Number formatting
# - Date/time formatting
"

create_file "dashboard/utils/charts.py" "\"\"\"Chart configuration helpers.\"\"\"
# TODO: Chart utilities
# - Plotly themes
# - Common configurations
"

# Test files
create_file "tests/conftest.py" "\"\"\"Pytest configuration and fixtures.\"\"\"
import pytest

# TODO: Add fixtures for:
# - Database connections
# - Redis connections
# - Mock data
"

create_file "tests/unit/test_metrics_calculator.py" "\"\"\"Test metric calculations.\"\"\"
import pytest

# TODO: Add tests for metric calculations
"

create_file "tests/unit/test_alert_engine.py" "\"\"\"Test alert engine.\"\"\"
import pytest

# TODO: Add tests for alert logic
"

create_file "tests/integration/test_database.py" "\"\"\"Test database operations.\"\"\"
import pytest

# TODO: Add integration tests for database
"

create_file "tests/e2e/test_full_pipeline.py" "\"\"\"End-to-end pipeline test.\"\"\"
import pytest

# TODO: Add E2E tests
"

# Script files
create_file "scripts/backfill_data.py" "#!/usr/bin/env python
\"\"\"Backfill historical order book data.\"\"\"

# TODO: Implement backfill logic
"

create_file "scripts/test_connection.py" "#!/usr/bin/env python
\"\"\"Test external connections.\"\"\"

# TODO: Test Binance, DB, Redis connections
"

create_file "scripts/benchmark.py" "#!/usr/bin/env python
\"\"\"Performance benchmarking.\"\"\"

# TODO: Benchmark metric calculations and DB writes
"

create_file "scripts/export_data.py" "#!/usr/bin/env python
\"\"\"Export data to CSV/Parquet.\"\"\"

# TODO: Implement data export
"

# Documentation
create_file "docs/ARCHITECTURE.md" "# System Architecture

TODO: Document system architecture
- High-level design
- Component interaction
- Data flow
"

create_file "docs/METRICS.md" "# Metric Definitions

TODO: Document all metrics
- Formulas
- Thresholds
- Interpretation
"

create_file "docs/API.md" "# API Documentation

TODO: Document APIs
- WebSocket endpoints
- Database schema
- Redis keys
"

create_file "docs/DEPLOYMENT.md" "# Deployment Guide

TODO: Production deployment guide
- Cloud deployment
- Kubernetes
- Monitoring
"

create_file "docs/TROUBLESHOOTING.md" "# Troubleshooting

TODO: Common issues and solutions
"

# VS Code settings
create_file ".vscode/settings.json" "{
    \"python.defaultInterpreterPath\": \"\${workspaceFolder}/.venv/bin/python\",
    \"python.linting.enabled\": true,
    \"python.linting.ruffEnabled\": true,
    \"python.formatting.provider\": \"black\",
    \"editor.formatOnSave\": true,
    \"editor.codeActionsOnSave\": {
        \"source.organizeImports\": true
    }
}
"

create_file ".vscode/launch.json" "{
    \"version\": \"0.2.0\",
    \"configurations\": [
        {
            \"name\": \"Python: Ingestion Service\",
            \"type\": \"python\",
            \"request\": \"launch\",
            \"program\": \"\${workspaceFolder}/src/ingestion/main.py\",
            \"console\": \"integratedTerminal\",
            \"envFile\": \"\${workspaceFolder}/.env\"
        },
        {
            \"name\": \"Python: Dashboard\",
            \"type\": \"python\",
            \"request\": \"launch\",
            \"module\": \"streamlit\",
            \"args\": [\"run\", \"dashboard/app.py\"],
            \"console\": \"integratedTerminal\",
            \"envFile\": \"\${workspaceFolder}/.env\"
        }
    ]
}
"

# GitHub workflow
create_file ".github/workflows/test.yml" "name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: timescale/timescaledb:latest-pg15
        env:
          POSTGRES_PASSWORD: test
      redis:
        image: redis:7-alpine
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Install uv
        uses: astral-sh/setup-uv@v1
        
      - name: Set up Python
        run: uv python install 3.11
        
      - name: Install dependencies
        run: uv pip install -e \".[dev]\"
        
      - name: Run tests
        run: pytest
"

# Placeholder data files
create_file "tests/fixtures/orderbook_snapshot.json" "{
    \"symbol\": \"BTCUSDT\",
    \"bids\": [[50000.0, 1.5], [49999.0, 2.0]],
    \"asks\": [[50001.0, 1.2], [50002.0, 1.8]]
}
"

# License
create_file "LICENSE" "MIT License

Copyright (c) 2024 [Your Name]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the \"Software\"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"

echo ""
echo "=================================================="
echo -e "${GREEN}✓ Directory structure created successfully!${NC}"
echo "=================================================="
echo ""
echo "Project structure:"
echo "  - Source code:     src/"
echo "  - Dashboard:       dashboard/"
echo "  - Tests:          tests/"
echo "  - Scripts:        scripts/"
echo "  - Documentation:  docs/"
echo ""
echo "Next steps:"
echo "  1. Activate virtual environment: source .venv/bin/activate"
echo "  2. Start Docker services: docker-compose up -d"
echo "  3. Start implementing the TODOs in each file!"
echo ""
echo "Happy coding! 🚀"