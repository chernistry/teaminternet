# Aporia Test - Automated Solution

## Overview

This solution automates the complete Aporia test workflow using Google Cloud CLI, eliminating all manual steps. The script fetches data from JSONBin API, converts to CSV, uploads to Google Sheets, and generates reports with visualizations.

## Architecture

**Stack**: Bash + gcloud CLI + Google Sheets/Drive APIs + jq + curl

**Approach**: Pure CLI automation - no manual clicks, no Apps Script, no Python dependencies.

## Prerequisites

- `gcloud` (Google Cloud CLI)
- `jq` (JSON processor)
- `curl`
- Google Cloud project with Sheets & Drive APIs enabled
- Authenticated gcloud session with Drive access

## Setup

1. **Install dependencies** (if not already installed):
```bash
# macOS
brew install jq

# Verify gcloud
gcloud --version
```

2. **Authenticate with proper scopes**:
```bash
gcloud auth login --enable-gdrive-access
gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/spreadsheets
```

3. **Set project**:
```bash
gcloud config set project teaminternet
```

## Usage

### One-time execution

```bash
./aporia_cli.sh
```

The script will:
1. Fetch JSON data from JSONBin API (2 bins)
2. Convert JSON to CSV with proper headers
3. Create source Google Sheet with 3 tabs:
   - `Raw_MediaBuyer` - Media buyer campaign data
   - `Raw_Campaign` - Campaign performance data
   - `Report` - Automated reports with QUERY formulas and charts
4. Create target Google Sheet
5. Copy data tabs from source to target (data transfer task)
6. Output URLs for both sheets

### Scheduled execution

Add to crontab for hourly updates:
```bash
crontab -e
# Add:
0 * * * * cd /Users/sasha/IdeaProjects/teaminternet && ./aporia_cli.sh >> aporia_cli.log 2>&1
```

## Configuration

Edit variables at the top of `aporia_cli.sh`:

```bash
PROJECT_ID="teaminternet"
SOURCE_SHEET_NAME="Aporia Test"
TARGET_SHEET_NAME="Aporia Target"
WORKDIR="./aporia_work"
```

## Output

The script creates:
- **Local files** in `aporia_work/`:
  - `campaign.json` - Raw campaign data
  - `media.json` - Raw media buyer data
  - `campaign_performance.csv` - Processed campaign CSV
  - `media_buyer.csv` - Processed media buyer CSV

- **Google Sheets**:
  - Source sheet with raw data + reports
  - Target sheet with copied data (data transfer requirement)

## Reports Generated

### Report Tab includes:

1. **Media Buyer Summary**
   - Total Revenue by Media Buyer
   - Total Spend by Media Buyer
   - ROI calculation: (Revenue - Spend) / Spend
   - Sorted by ROI descending

2. **Campaign Performance**
   - Revenue by Platform/Offer/Country
   - Total Leads
   - Revenue Per Lead (RPL)
   - Sorted by Revenue descending

3. **Visualizations**
   - Column chart: Revenue vs Spend by Media Buyer (with ROI on secondary axis)
   - Column chart: Top Platforms/Offers by Revenue (with Leads and RPL)

## Technical Details

### Data Transformation

- **JSONBin API**: Fetches with `X-Access-Key` header, `?meta=false` for raw arrays
- **CSV conversion**: Uses `jq` with proper type coercion (numbers, strings)
- **Headers**: Matches exact column names from task requirements

### Google Sheets Operations

- **Creation**: Drive API v3 `files.create` with Sheets MIME type
- **Tab management**: Sheets API v4 `batchUpdate` for rename/add sheets
- **Data import**: `pasteData` request with CSV delimiter
- **Formulas**: `QUERY` with `INDIRECT` for dynamic references
- **Charts**: `addChart` with `basicChart` spec (column type, dual axis)
- **Data transfer**: `sheets.copyTo` for efficient tab duplication

### Reliability

- **Idempotent**: Each run creates fresh sheets (can be modified to update existing)
- **Error handling**: `set -euo pipefail` for fail-fast
- **Auth**: Uses `gcloud auth print-access-token` for OAuth
- **Quotas**: Minimal API calls (~10 per run), well within limits

## Verification

After running, verify:

1. **Source Sheet** (`Aporia Test`):
   - ✅ 3 tabs present
   - ✅ Raw data populated with correct headers
   - ✅ Report tab shows 2 QUERY tables
   - ✅ 2 charts visible and rendering

2. **Target Sheet** (`Aporia Target`):
   - ✅ 2 tabs copied from source
   - ✅ Data matches source exactly

3. **Local files**:
   - ✅ CSV files in `aporia_work/` with proper formatting

## Extending

### Add more reports

Edit `build_report()` function to add more QUERY formulas or charts.

### Update existing sheets

Modify script to:
1. Check if sheet exists by name
2. Clear existing data
3. Paste new data
4. Preserve sheet IDs

### Add Apps Script automation

For scheduled updates within Sheets:
1. Create time-driven trigger
2. Call external endpoint that runs this script
3. Or rewrite core logic in Apps Script

## Troubleshooting

**403 Insufficient Permission**:
```bash
gcloud auth login --enable-gdrive-access
```

**Missing jq**:
```bash
brew install jq  # macOS
```

**API not enabled**:
```bash
gcloud services enable sheets.googleapis.com drive.googleapis.com
```

**Invalid JSON from JSONBin**:
- Check API key is correct
- Verify bin IDs haven't changed
- Test with curl manually

## Security

- JSONBin API key is in script (acceptable for test; use env var for production)
- OAuth tokens managed by gcloud (stored in `~/.config/gcloud/`)
- No secrets committed to version control
- Sheets created with user's Drive permissions

## Performance

- **Execution time**: ~5-10 seconds
- **API calls**: ~10 per run
- **Data size**: Handles thousands of rows efficiently
- **Scalability**: For >10K rows, consider batching or Apps Script continuation

## References

- [Google Sheets API v4](https://developers.google.com/sheets/api)
- [Google Drive API v3](https://developers.google.com/drive/api)
- [JSONBin API](https://jsonbin.io/api-reference)
- [jq Manual](https://stedolan.github.io/jq/manual/)

## License

Internal test solution for Team Internet hiring process.
