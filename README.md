# Strava Cycling Data ETL Pipeline

An automated ETL (Extract, Transform, Load) pipeline that extracts personal cycling data from the Strava API, cleans it for geospatial and metric analysis, and exports optimized CSV files for Tableau Public visualization.

## ⚡ Quick Start

```bash
# 1. Clone repository
git clone https://github.com/yourusername/Strava.git
cd Strava

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup credentials
cp .env.example .env
# Edit .env with your Strava API credentials

# 5. Run pipeline (includes OAuth authorization on first run)
python main.py
```

## 📋 What It Does

1. **Extracts** 12 months of cycling activities from Strava API
2. **Decodes** GPS polylines into latitude/longitude coordinates
3. **Transforms** data: unit conversions, date parsing, metric calculations
4. **Outputs** 2 CSV files ready for Tableau:
   - `cycling_summary.csv` - aggregated activity metrics
   - `cycling_paths.csv` - GPS points for route mapping

## 📁 Project Structure

```
Strava/
├── src/
│   ├── auth/
│   │   └── strava_auth.py              # OAuth2 authentication
│   ├── extraction/
│   │   └── strava_extractor.py         # Strava API data extraction
│   ├── transformation/
│   │   └── data_transformer.py         # Data cleaning & metrics
│   ├── utils/
│   │   ├── config.py                   # Configuration management
│   │   └── data_quality.py             # Data validation
│   └── __init__.py
├── config/
│   └── strava_tokens.json              # (auto-generated)
├── data/
│   ├── raw_activities.json             # (auto-generated)
│   ├── cycling_summary.csv             # (auto-generated)
│   └── cycling_paths.csv               # (auto-generated)
├── main.py                             # Pipeline orchestrator
├── requirements.txt                    # Python dependencies
├── .env.example                        # Credentials template
├── .gitignore                          # Git ignore rules
├── README.md                           # This file
└── PROJECT_DOCUMENTATION.txt           # Detailed documentation
```

## 🔧 Setup Instructions

### 1. Strava API Credentials

Create a Strava app at [https://www.strava.com/settings/apps](https://www.strava.com/settings/apps):
- Click "Create an app"
- Fill in application details
- Accept terms and create
- Copy **Client ID** and **Client Secret**

### 2. Environment Configuration

```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```
STRAVA_CLIENT_ID=your_client_id_here
STRAVA_CLIENT_SECRET=your_client_secret_here
MONTHS_BACK=12
```

### 3. Virtual Environment & Dependencies

```bash
python -m venv .venv
.venv\Scripts\activate              # Windows PowerShell
source .venv/bin/activate           # macOS/Linux bash

pip install -r requirements.txt
```

### 4. First Run - OAuth Authorization

```bash
python main.py --force
```

The script will:
1. Prompt you with a Strava authorization URL
2. Ask you to authorize the app
3. Ask you to paste the authorization code
4. Automatically save your token
5. Extract, transform, and generate CSV files

## 🚀 Usage

### Basic Commands

```bash
# Run pipeline (uses cache if <24h old)
python main.py

# Force fresh extraction (ignore cache)
python main.py --force

# Extract last 6 months instead of 12
python main.py --months 6

# Extract from absolute date (rebaselining historical data)
python main.py --start-date 2025-07-17 --force

# Combine options
python main.py --force --months 3

# Show all options
python main.py --help
```

### Advanced: Historical Data Rebaselining

To capture historical activities starting from a specific date:

```bash
python main.py --start-date YYYY-MM-DD --force
```

Example: Rebaseline dataset from July 17, 2025:
```bash
python main.py --start-date 2025-07-17 --force
```

**Note**: Using `--start-date` overrides the `--months` option. Use `--force` to ensure cache is cleared and the new date range is processed.

### Output Files

**cycling_summary.csv**
- One row per activity
- Columns: Activity_ID, Name, Type, Distance_KM, Elevation_M, Average_Speed_KMH, etc.
- Ready for Tableau dashboard creation

**cycling_paths.csv**
- One row per GPS coordinate point
- Columns: Activity_ID, Point_Index, Latitude, Longitude
- Use with Tableau "Path" visualization for route mapping

## ✨ Features

- **✓ OAuth2 Auto-Refresh**: Token automatically refreshes without re-authentication
- **✓ Flexible Date Filtering**: Choose between relative (--months) or absolute (--start-date) date ranges
- **✓ Geospatial Data**: GPS polylines decoded for Tableau mapping
- **✓ Smart Caching**: Skips extraction if data <24h old
- **✓ Data Quality**: Removes duplicates, filters invalid activities
- **✓ Performance Metrics**: Average speed, pace, elevation gain
- **✓ Time Series**: Date components (Year, Month, Day, DoW) for analysis
- **✓ Tableau Ready**: ISO-8601 dates, human-readable headers
- **✓ Comprehensive Logging**: Track pipeline progress and issues
- **✓ Production Ready**: Comprehensive documentation and unit tests

## 📊 Output Examples

### cycling_summary.csv (72 activities example)
```
Activity_ID  | Activity_Name        | Activity_Type | Distance_KM | Elevation_M | Average_Speed_KMH | Date
12345678901  | Morning Commute       | Road Bike     | 12.4        | 45.2        | 24.5              | 2026-01-27
12345678902  | Weekend Ride          | Road Bike     | 45.6        | 320.1       | 28.3              | 2026-01-26
...
```

### cycling_paths.csv (9,178 points example)
```
Activity_ID  | Point_Index | Latitude  | Longitude
12345678901  | 0           | 53.3498   | -6.2603
12345678901  | 1           | 53.3502   | -6.2605
12345678901  | 2           | 53.3506   | -6.2607
...
```

## ⚙️ Configuration Options

Edit `.env` to customize:

```env
# Strava API Credentials (required)
STRAVA_CLIENT_ID=your_id
STRAVA_CLIENT_SECRET=your_secret
STRAVA_REFRESH_TOKEN=auto_filled_first_run

# Output Settings
OUTPUT_DIR=./data
OUTPUT_FILENAME=cycling_activities_2025.csv
MONTHS_BACK=12
ACTIVITIES_PER_PAGE=200
```

## 🔐 Security Notes

- ✓ `.env` file is in `.gitignore` - credentials never committed
- ✓ `config/strava_tokens.json` is in `.gitignore` - tokens never exposed
- ✓ OAuth uses secure refresh token flow
- ✓ All secrets handled via environment variables

## 🐛 Troubleshooting

**"ModuleNotFoundError: No module named 'stravalib'"**
```bash
pip install -r requirements.txt
```

**"Missing STRAVA_CLIENT_ID in .env"**
```bash
cp .env.example .env
# Edit .env with your credentials
```

**"Token expired"**
```bash
# Delete token file, script will re-authenticate
rm config/strava_tokens.json
python main.py --force
```

## 📚 Detailed Documentation

See [PROJECT_DOCUMENTATION.txt](PROJECT_DOCUMENTATION.txt) for:
- Complete architecture overview
- Step-by-step implementation details
- Data flow diagrams
- API rate limits and performance
- Future enhancement ideas

## 🧪 Testing

### Run Unit Tests

```bash
# Install test dependencies (already in requirements.txt)
pip install pytest pytest-cov

# Run all tests
pytest tests/

# Run with coverage report
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_caching.py -v

# Run specific test class
pytest tests/test_transformer.py::TestMetricCalculations -v
```

### Test Coverage

The project includes **120+ unit tests** covering:
- **Extraction**: Date calculation, activity data extraction, start-date feature
- **Transformation**: Unit conversions, metric calculations, date decomposition, polyline decoding
- **Caching**: Cache age, validity, force override, refresh logic
- **Error Handling**: Missing data, invalid formats, edge cases

Expected Results: All tests pass, >80% code coverage

## 🔄 Scheduling (Optional)

### Windows Task Scheduler
```
Action: python main.py
Directory: C:\Users\YourUser\Strava
Schedule: Daily at 2 AM
```

### Linux/macOS Cron
```bash
0 2 * * 0 cd /path/to/Strava && python main.py
```

## 📈 Expected Performance

- **Extraction**: 1-2 seconds per 100 activities
- **Transformation**: <1 second
- **API Calls**: 1-5 per run (within Strava's 600/15-min limit)
- **Cache Benefit**: 95%+ faster on subsequent runs within 24h

## 📝 Requirements Met

- ✓ OAuth2 authentication with automatic token refresh
- ✓ 12-month activity extraction with pagination
- ✓ Unit conversion (meters→km, seconds→minutes)
- ✓ Date decomposition and ISO-8601 formatting
- ✓ GPS polyline decoding for geospatial analysis
- ✓ Commute vs Leisure classification
- ✓ Duplicate and invalid activity removal
- ✓ Two CSV outputs optimized for Tableau
- ✓ Smart caching with force override
- ✓ Comprehensive error logging

## 📞 Support

For issues:
1. Check [PROJECT_DOCUMENTATION.txt](PROJECT_DOCUMENTATION.txt)
2. Review Strava API docs: [https://developers.strava.com](https://developers.strava.com)
3. Check stravalib docs: [https://stravalib.readthedocs.io](https://stravalib.readthedocs.io)

## 📄 License

This project respects Strava's terms of service. See [https://www.strava.com/legal](https://www.strava.com/legal)

## Streamlit Dashboard

This project now includes a personalized Streamlit dashboard:

- App file: `dashboard/app.py`
- Run script: `run_dashboard.bat`
- Full docs: `DASHBOARD.md`

Start dashboard:

```bash
streamlit run dashboard/app.py
```

Or:

```bash
run_dashboard.bat
```

Dashboard URL:

- `http://localhost:8501`

## Daily Update Policy (Current)

Pipeline update mode is now daily-only (not real-time).

- Use `run_pipeline.bat` in Windows Task Scheduler once per day at a fixed time.
- `run_near_realtime.bat` has been removed.
- Dashboard (`dashboard/app.py`) no longer triggers ETL refreshes on demand.
- Dashboard shows the last ETL update timestamp from CSV file modification time.

## Streamlit Cloud Deployment (Recommended)

Use Streamlit Community Cloud for the easiest public showcase:

1. Push this repo to GitHub.
2. Create a new app in Streamlit Cloud.
3. Set main file path to `dashboard/app.py`.
4. Deploy and share the app URL.

Recommended app settings:
- `SHOWCASE_MODE=true`
- `REQUIRE_GATEWAY_AUTH=false`

Optional later:
- Cloudflare/Supabase access controls can be added later, but are not required for Streamlit deployment.
