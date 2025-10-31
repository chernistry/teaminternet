# Aporia Test - Automated Solution

## Overview

Python automation for Aporia test: fetches data from JSONBin API, converts to DataFrames, uploads to Google Sheets with reports and visualizations.

**Stack**: Python + google-api-python-client + pandas + gcloud auth + python-dotenv

## Prerequisites

- Python 3.12+
- `gcloud` CLI (authenticated)
- Google Cloud project with Sheets & Drive APIs enabled

## Setup

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Authenticate gcloud**:
```bash
gcloud auth login --enable-gdrive-access
gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/spreadsheets
gcloud config set project YOUR_PROJECT_ID
```

4. **Enable APIs**:
```bash
gcloud services enable sheets.googleapis.com drive.googleapis.com
```

## Usage

```bash
python3 aporia.py
```

The script will:
1. Load configuration from `.env` file
2. Fetch JSON from JSONBin (2 bins: campaign + media buyer data)
3. Convert to pandas DataFrames with proper types
4. Create source Google Sheet in configured folder with 3 tabs:
   - `Raw_MediaBuyer` - Media buyer campaign data
   - `Raw_Campaign` - Campaign performance data
   - `Report` - Automated analytics with QUERY formulas and charts
5. Create target Google Sheet
6. Copy all 3 tabs to target (data transfer requirement)
7. Output URLs for both sheets

## Configuration

All configuration is now managed via environment variables in `.env` file:

```bash
# Copy example and edit with your values
cp .env.example .env
```

Optional variables:
- `SOURCE_SHEET_NAME` - Name for source spreadsheet (default: "Aporia Test")
- `TARGET_SHEET_NAME` - Name for target spreadsheet (default: "Aporia Target")
- `TAB_MEDIA` - Media buyer tab name (default: "Raw_MediaBuyer")
- `TAB_CAMPAIGN` - Campaign tab name (default: "Raw_Campaign")
- `TAB_REPORT` - Report tab name (default: "Report")

See `.env.example` for detailed setup instructions and links.

## Output

**Google Sheets created in Drive folder**:
- Source: 3 tabs with raw data + reports
- Target: 3 tabs copied from source

**Report Tab includes**:

1. **Media Buyer Summary**
   - Total Revenue by Media Buyer
   - Total Spend by Media Buyer
   - ROI: (Revenue - Spend) / Spend

2. **Campaign Performance**
   - Revenue by Platform/Offer/Country
   - Total Leads
   - Revenue Per Lead (RPL)

3. **Visualizations**
   - Column chart: Revenue vs Spend by Media Buyer
   - Column chart: Top Platforms/Offers by Revenue

## Technical Details

### Data Sources
- **JSONBin API**: 2 bins with campaign and media buyer data
- **Authentication**: gcloud OAuth token via `subprocess`
- **APIs**: Drive v3 (create files), Sheets v4 (batchUpdate, copyTo)

### Data Transformation
- pandas for JSON → DataFrame conversion
- Numeric type coercion for Revenue/Spend columns
- Column renaming to match task requirements

### Google Sheets Operations
- `files.create` - create spreadsheets in folder
- `batchUpdate` - rename/add tabs, paste formulas, add charts
- `values.update` with `USER_ENTERED` - upload data with type inference
- `sheets.copyTo` - efficient tab duplication between sheets

## Files

```
aporia.py           - Main Python script
requirements.txt    - Python dependencies
.env.example        - Environment configuration template
.env                - Your environment configuration (create from example)
task.md            - Original task description
README.md          - This file
```

## Troubleshooting

**403 Insufficient Permission**:
```bash
gcloud auth login --enable-gdrive-access
```

**Import errors**:
```bash
pip install -r requirements.txt
```

**API not enabled**:
```bash
gcloud services enable sheets.googleapis.com drive.googleapis.com
```

## Task Requirements Met

✅ **Step 1**: API data retrieval and CSV conversion (via pandas)  
✅ **Step 2**: Google Sheets upload with proper columns  
✅ **Task 1**: Automated data transfer (copyTo API)  
✅ **Task 2**: Reports with meaningful insights and visualizations

## References

- [Google Sheets API v4](https://developers.google.com/sheets/api)
- [Google Drive API v3](https://developers.google.com/drive/api)
- [JSONBin API](https://jsonbin.io/api-reference)
- [pandas Documentation](https://pandas.pydata.org/docs/)
