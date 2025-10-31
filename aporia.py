#!/usr/bin/env python3
"""
Aporia Test - Automated Google Sheets Data Pipeline.

This module automates the extraction of campaign and media buyer data from
JSONBin API, transforms it using pandas, and uploads it to Google Sheets with
automated reports and visualizations.
"""

# ==== STANDARD LIBRARY IMPORTS ==== #
import argparse
import json
import os
import subprocess
from typing import Any, Dict, List, Optional


# ==== THIRD-PARTY IMPORTS ==== #
import pandas as pd
import requests
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# ==== ENVIRONMENT CONFIGURATION ==== #
load_dotenv()

PROJECT_ID: Optional[str] = os.getenv("PROJECT_ID")
FOLDER_ID: Optional[str] = os.getenv("FOLDER_ID")
JSONBIN_KEY: Optional[str] = os.getenv("JSONBIN_KEY")
BIN_CAMPAIGN: Optional[str] = os.getenv("BIN_CAMPAIGN")
BIN_MEDIA: Optional[str] = os.getenv("BIN_MEDIA")
SOURCE_SHEET_NAME: Optional[str] = os.getenv("SOURCE_SHEET_NAME")
TARGET_SHEET_NAME: Optional[str] = os.getenv("TARGET_SHEET_NAME")
TAB_MEDIA: Optional[str] = os.getenv("TAB_MEDIA")
TAB_CAMPAIGN: Optional[str] = os.getenv("TAB_CAMPAIGN")
TAB_REPORT: Optional[str] = os.getenv("TAB_REPORT")
TAB_REPORT_BUYER: Optional[str] = (
    os.getenv("TAB_REPORT_BUYER") or "Report_MediaBuyerSummary"
)
TAB_REPORT_CAMP: Optional[str] = (
    os.getenv("TAB_REPORT_CAMP") or "Report_CampaignPerformance"
)



# ==== AUTHENTICATION MODULE ==== #


def get_credentials() -> Credentials:
    """
    Retrieve OAuth credentials from gcloud CLI.

    Returns:
        Credentials: Google OAuth2 credentials object with access token.

    Raises:
        subprocess.CalledProcessError: If gcloud command fails.
    """
    token = (
        subprocess.check_output(["gcloud", "auth", "print-access-token"])
        .decode()
        .strip()
    )
    return Credentials(token=token)



# ==== DATA EXTRACTION MODULE ==== #


def fetch_jsonbin(bin_id: str) -> List[Dict[str, Any]]:
    """
    Fetch data from JSONBin API.

    Args:
        bin_id (str): The unique identifier for the JSONBin.

    Returns:
        List[Dict[str, Any]]: Parsed JSON data as a list of dictionaries.

    Raises:
        requests.HTTPError: If the API request fails.
        requests.Timeout: If the request exceeds 30 seconds.
    """
    url = f"https://api.jsonbin.io/v3/b/{bin_id}/latest?meta=false"
    headers = {"X-Access-Key": JSONBIN_KEY}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()



# ==== GOOGLE DRIVE FILE MANAGEMENT ==== #


def find_existing_file(
    drive_service: Any,
    name: str,
    folder_id: str
) -> Optional[str]:
    """
    Search for an existing file by name in a specific Google Drive folder.

    Args:
        drive_service (Any): Google Drive API service instance.
        name (str): Name of the file to search for.
        folder_id (str): Google Drive folder ID to search within.

    Returns:
        Optional[str]: File ID if found, None otherwise.
    """
    query = f"name='{name}' and '{folder_id}' in parents and trashed=false"
    results = drive_service.files().list(
        q=query,
        fields="files(id, name)"
    ).execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None



def delete_file(drive_service: Any, file_id: str) -> None:
    """
    Delete a file from Google Drive by its ID.

    Args:
        drive_service (Any): Google Drive API service instance.
        file_id (str): The unique identifier of the file to delete.
    """
    drive_service.files().delete(fileId=file_id).execute()



def create_sheet(
    drive_service: Any,
    name: str,
    force: bool = False
) -> str:
    """
    Create a new Google Spreadsheet in a specified folder.

    Args:
        drive_service (Any): Google Drive API service instance.
        name (str): Name for the new spreadsheet.
        force (bool): If True, delete existing file with same name before
            creating. Defaults to False.

    Returns:
        str: The ID of the newly created spreadsheet.
    """
    if force:
        existing_id = find_existing_file(drive_service, name, FOLDER_ID)
        if existing_id:
            print(f"  Deleting existing '{name}'...")
            delete_file(drive_service, existing_id)

    body = {
        "name": name,
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "parents": [FOLDER_ID],
    }
    file = drive_service.files().create(body=body, fields="id").execute()
    return file["id"]



# ==== GOOGLE SHEETS OPERATIONS ==== #


def setup_tabs(
    sheets_service: Any,
    spreadsheet_id: str,
    tab_names: List[str]
) -> None:
    """
    Configure spreadsheet tabs by renaming the first tab and adding new ones.

    Args:
        sheets_service (Any): Google Sheets API service instance.
        spreadsheet_id (str): The ID of the target spreadsheet.
        tab_names (List[str]): List of tab names. First name renames the
            default tab, remaining names create new tabs.
    """
    requests = [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": 0, "title": tab_names[0]},
                "fields": "title",
            }
        }
    ]
    for name in tab_names[1:]:
        requests.append({"addSheet": {"properties": {"title": name}}})

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body={"requests": requests}
    ).execute()



def upload_dataframe(
    sheets_service: Any,
    spreadsheet_id: str,
    sheet_name: str,
    df: pd.DataFrame
) -> None:
    """
    Upload a pandas DataFrame to a Google Sheets tab.

    Args:
        sheets_service (Any): Google Sheets API service instance.
        spreadsheet_id (str): The ID of the target spreadsheet.
        sheet_name (str): Name of the tab to upload data to.
        df (pd.DataFrame): DataFrame containing the data to upload.
    """
    values = [df.columns.tolist()] + df.values.tolist()
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()



# ==== REPORT GENERATION MODULE ==== #


def add_report_formulas(
    sheets_service: Any,
    spreadsheet_id: str,
    top_n: int = 25
) -> None:
    """
    Create separate report sheets with QUERY formulas for analysis.

    Generates two report tabs:
    1. Media Buyer Summary: Revenue, Spend, and ROI by buyer
    2. Campaign Performance: Top N campaigns by revenue with metrics

    Args:
        sheets_service (Any): Google Sheets API service instance.
        spreadsheet_id (str): The ID of the target spreadsheet.
        top_n (int): Number of top campaigns to display. Defaults to 25.
    """
    meta = sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id
    ).execute()
    buyer_sheet_id = next(
        s["properties"]["sheetId"]
        for s in meta["sheets"]
        if s["properties"]["title"] == TAB_REPORT_BUYER
    )
    camp_sheet_id = next(
        s["properties"]["sheetId"]
        for s in meta["sheets"]
        if s["properties"]["title"] == TAB_REPORT_CAMP
    )

    reqs = [
        {
            "updateCells": {
                "range": {
                    "sheetId": buyer_sheet_id,
                    "startRowIndex": 0,
                    "startColumnIndex": 0,
                },
                "rows": [
                    {
                        "values": [
                            {
                                "userEnteredValue": {
                                    "stringValue": (
                                        "Media Buyer Summary "
                                        "(Revenue, Spend, ROI)"
                                    )
                                }
                            }
                        ]
                    },
                    {"values": []},
                    {
                        "values": [
                            {
                                "userEnteredValue": {
                                    "formulaValue": (
                                        f"=QUERY({TAB_MEDIA}!A2:E, "
                                        '"select Col1, sum(Col4), sum(Col5), '
                                        "(sum(Col4)-sum(Col5))/sum(Col5) "
                                        "where Col1 is not null "
                                        "group by Col1 "
                                        "order by (sum(Col4)-sum(Col5))/sum(Col5) desc "
                                        "label sum(Col4) 'Total Revenue', "
                                        "sum(Col5) 'Total Spend', "
                                        '(sum(Col4)-sum(Col5))/sum(Col5) \'ROI\'", 0)'
                                    )
                                }
                            }
                        ]
                    },
                ],
                "fields": "userEnteredValue",
            }
        },
        {
            "updateCells": {
                "range": {
                    "sheetId": camp_sheet_id,
                    "startRowIndex": 0,
                    "startColumnIndex": 0,
                },
                "rows": [
                    {
                        "values": [
                            {
                                "userEnteredValue": {
                                    "stringValue": (
                                        f"Campaign Performance "
                                        f"(Revenue, Leads, RPL) — Top {top_n}"
                                    )
                                }
                            }
                        ]
                    },
                    {"values": []},
                    {
                        "values": [
                            {
                                "userEnteredValue": {
                                    "formulaValue": (
                                        f"=QUERY({TAB_CAMPAIGN}!A2:H, "
                                        '"select Col1, Col2, Col3, sum(Col5), '
                                        "sum(Col6), sum(Col5)/sum(Col6) "
                                        "where Col1 is not null "
                                        "group by Col1, Col2, Col3 "
                                        f"order by sum(Col5) desc limit {top_n} "
                                        "label sum(Col5) 'Total Revenue', "
                                        "sum(Col6) 'Total Leads', "
                                        'sum(Col5)/sum(Col6) \'RPL\'", 0)'
                                    )
                                }
                            }
                        ]
                    },
                ],
                "fields": "userEnteredValue",
            }
        },
        {
            "updateCells": {
                "range": {
                    "sheetId": camp_sheet_id,
                    "startRowIndex": 2,
                    "startColumnIndex": 6,
                },
                "rows": [
                    {
                        "values": [
                            {
                                "userEnteredValue": {
                                    "formulaValue": (
                                        '=ARRAYFORMULA(IF(A3:A="","", '
                                        'A3:A & " | " & B3:B & " | " & C3:C))'
                                    )
                                }
                            }
                        ]
                    }
                ],
                "fields": "userEnteredValue",
            }
        },
    ]
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body={"requests": reqs}
    ).execute()

    # --► NUMBER FORMATTING
    fmt = [
        {
            "repeatCell": {
                "range": {
                    "sheetId": buyer_sheet_id,
                    "startRowIndex": 2,
                    "startColumnIndex": 1,
                    "endColumnIndex": 3,
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}
                    }
                },
                "fields": "userEnteredFormat.numberFormat",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": buyer_sheet_id,
                    "startRowIndex": 2,
                    "startColumnIndex": 3,
                    "endColumnIndex": 4,
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {"type": "PERCENT", "pattern": "0.00%"}
                    }
                },
                "fields": "userEnteredFormat.numberFormat",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": camp_sheet_id,
                    "startRowIndex": 2,
                    "startColumnIndex": 3,
                    "endColumnIndex": 4,
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}
                    }
                },
                "fields": "userEnteredFormat.numberFormat",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": camp_sheet_id,
                    "startRowIndex": 2,
                    "startColumnIndex": 4,
                    "endColumnIndex": 5,
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {"type": "NUMBER", "pattern": "#,##0"}
                    }
                },
                "fields": "userEnteredFormat.numberFormat",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": camp_sheet_id,
                    "startRowIndex": 2,
                    "startColumnIndex": 5,
                    "endColumnIndex": 6,
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {"type": "PERCENT", "pattern": "0.00%"}
                    }
                },
                "fields": "userEnteredFormat.numberFormat",
            }
        },
    ]
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body={"requests": fmt}
    ).execute()



# ==== VISUALIZATION MODULE ==== #


def add_charts(
    sheets_service: Any,
    spreadsheet_id: str,
    buyers_count: int,
    top_n: int = 25
) -> None:
    """
    Create visualization charts on separate sheets.

    Generates two charts:
    1. Combo chart: Revenue & Spend bars with ROI line for media buyers
    2. Horizontal bar chart: Top campaigns by revenue with RPL line

    Args:
        sheets_service (Any): Google Sheets API service instance.
        spreadsheet_id (str): The ID of the target spreadsheet.
        buyers_count (int): Number of unique media buyers for chart sizing.
        top_n (int): Number of top campaigns to visualize. Defaults to 25.
    """
    meta = sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id
    ).execute()
    buyer_sheet_id = next(
        s["properties"]["sheetId"]
        for s in meta["sheets"]
        if s["properties"]["title"] == TAB_REPORT_BUYER
    )
    camp_sheet_id = next(
        s["properties"]["sheetId"]
        for s in meta["sheets"]
        if s["properties"]["title"] == TAB_REPORT_CAMP
    )

    def ensure_sheet(title: str) -> int:
        """Create chart sheet if it doesn't exist."""
        for s in meta["sheets"]:
            if s["properties"]["title"] == title:
                return s["properties"]["sheetId"]
        r = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
        ).execute()
        return r["replies"][0]["addSheet"]["properties"]["sheetId"]

    chart_buyer_id = ensure_sheet("Chart_Buyer")
    chart_camp_id = ensure_sheet("Chart_Campaign")

    # --► COMPUTE TIGHT DATA RANGES
    buyer_start = 2
    buyer_end = buyer_start + 1 + max(buyers_count or 0, 0)
    camp_start = 2
    camp_end = camp_start + 1 + max(top_n or 0, 0)

    # --► BUYER COMBO CHART: Revenue/Spend bars + ROI line
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "addChart": {
                        "chart": {
                            "spec": {
                                "title": "Revenue & Spend with ROI by Media Buyer",
                                "basicChart": {
                                    "chartType": "COMBO",
                                    "legendPosition": "BOTTOM_LEGEND",
                                    "domains": [
                                        {
                                            "domain": {
                                                "sourceRange": {
                                                    "sources": [
                                                        {
                                                            "sheetId": buyer_sheet_id,
                                                            "startRowIndex": buyer_start,
                                                            "endRowIndex": buyer_end,
                                                            "startColumnIndex": 0,
                                                            "endColumnIndex": 1,
                                                        }
                                                    ]
                                                }
                                            }
                                        }
                                    ],
                                    "series": [
                                        {
                                            "series": {
                                                "sourceRange": {
                                                    "sources": [
                                                        {
                                                            "sheetId": buyer_sheet_id,
                                                            "startRowIndex": buyer_start,
                                                            "endRowIndex": buyer_end,
                                                            "startColumnIndex": 1,
                                                            "endColumnIndex": 2,
                                                        }
                                                    ]
                                                }
                                            },
                                            "type": "COLUMN",
                                        },
                                        {
                                            "series": {
                                                "sourceRange": {
                                                    "sources": [
                                                        {
                                                            "sheetId": buyer_sheet_id,
                                                            "startRowIndex": buyer_start,
                                                            "endRowIndex": buyer_end,
                                                            "startColumnIndex": 2,
                                                            "endColumnIndex": 3,
                                                        }
                                                    ]
                                                }
                                            },
                                            "type": "COLUMN",
                                        },
                                        {
                                            "series": {
                                                "sourceRange": {
                                                    "sources": [
                                                        {
                                                            "sheetId": buyer_sheet_id,
                                                            "startRowIndex": buyer_start,
                                                            "endRowIndex": buyer_end,
                                                            "startColumnIndex": 3,
                                                            "endColumnIndex": 4,
                                                        }
                                                    ]
                                                }
                                            },
                                            "targetAxis": "RIGHT_AXIS",
                                            "type": "LINE",
                                        },
                                    ],
                                    "headerCount": 1,
                                },
                            },
                            "position": {
                                "overlayPosition": {
                                    "anchorCell": {
                                        "sheetId": chart_buyer_id,
                                        "rowIndex": 0,
                                        "columnIndex": 0,
                                    }
                                }
                            },
                        }
                    }
                }
            ]
        },
    ).execute()

    # --► CAMPAIGN HORIZONTAL BAR: Composite key domain + Revenue/RPL series
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "addChart": {
                        "chart": {
                            "spec": {
                                "title": (
                                    "Top Campaigns by Revenue "
                                    "(Platform | Offer | Country)"
                                ),
                                "basicChart": {
                                    "chartType": "BAR",
                                    "legendPosition": "BOTTOM_LEGEND",
                                    "domains": [
                                        {
                                            "domain": {
                                                "sourceRange": {
                                                    "sources": [
                                                        {
                                                            "sheetId": camp_sheet_id,
                                                            "startRowIndex": camp_start,
                                                            "endRowIndex": camp_end,
                                                            "startColumnIndex": 6,
                                                            "endColumnIndex": 7,
                                                        }
                                                    ]
                                                }
                                            }
                                        }
                                    ],
                                    "series": [
                                        {
                                            "series": {
                                                "sourceRange": {
                                                    "sources": [
                                                        {
                                                            "sheetId": camp_sheet_id,
                                                            "startRowIndex": camp_start,
                                                            "endRowIndex": camp_end,
                                                            "startColumnIndex": 3,
                                                            "endColumnIndex": 4,
                                                        }
                                                    ]
                                                }
                                            }
                                        },
                                        {
                                            "series": {
                                                "sourceRange": {
                                                    "sources": [
                                                        {
                                                            "sheetId": camp_sheet_id,
                                                            "startRowIndex": camp_start,
                                                            "endRowIndex": camp_end,
                                                            "startColumnIndex": 5,
                                                            "endColumnIndex": 6,
                                                        }
                                                    ]
                                                }
                                            },
                                            "type": "LINE",
                                        },
                                    ],
                                    "headerCount": 1,
                                },
                            },
                            "position": {
                                "overlayPosition": {
                                    "anchorCell": {
                                        "sheetId": chart_camp_id,
                                        "rowIndex": 0,
                                        "columnIndex": 0,
                                    }
                                }
                            },
                        }
                    }
                }
            ]
        },
    ).execute()



# ==== DATA TRANSFER MODULE ==== #


def copy_sheet(
    sheets_service: Any,
    source_id: str,
    sheet_name: str,
    target_id: str
) -> None:
    """
    Copy a sheet from source spreadsheet to target spreadsheet.

    Args:
        sheets_service (Any): Google Sheets API service instance.
        source_id (str): The ID of the source spreadsheet.
        sheet_name (str): Name of the sheet to copy.
        target_id (str): The ID of the destination spreadsheet.
    """
    meta = sheets_service.spreadsheets().get(spreadsheetId=source_id).execute()
    sheet_id = next(
        s["properties"]["sheetId"]
        for s in meta["sheets"]
        if s["properties"]["title"] == sheet_name
    )

    result = (
        sheets_service.spreadsheets()
        .sheets()
        .copyTo(
            spreadsheetId=source_id,
            sheetId=sheet_id,
            body={"destinationSpreadsheetId": target_id},
        )
        .execute()
    )

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=target_id,
        body={
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": result["sheetId"],
                            "title": sheet_name,
                        },
                        "fields": "title",
                    }
                }
            ]
        },
    ).execute()



# ==== MAIN EXECUTION PIPELINE ==== #


def main() -> None:
    """
    Execute the complete data pipeline workflow.

    Pipeline stages:
    1. Fetch data from JSONBin API
    2. Transform data using pandas
    3. Create Google Sheets structure
    4. Upload data to sheets
    5. Generate reports with formulas
    6. Create visualizations
    7. Transfer data to target sheet
    """
    parser = argparse.ArgumentParser(description="Aporia Test Automation")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing sheets with same names",
    )
    args = parser.parse_args()

    print("[1] Fetching data from JSONBin...")
    campaign_data = fetch_jsonbin(BIN_CAMPAIGN)
    media_data = fetch_jsonbin(BIN_MEDIA)

    print("[2] Converting to DataFrames...")
    df_campaign = pd.DataFrame(campaign_data)
    df_campaign = df_campaign.rename(
        columns={
            "Platform": "Platform",
            "offer": "Offer",
            "country": "Country",
            "adtitle": "Ad Title",
            "Revenue": "Revenue Prediction",
            "Leads": "Leads",
            "Revenue Per Leads": "Revenue Per Lead",
            "top_10_keywords": "Top 10 Keywords",
        }
    )

    df_media = pd.DataFrame(media_data)
    df_media["Revenue"] = pd.to_numeric(df_media["Revenue"], errors="coerce")
    df_media["Spend"] = pd.to_numeric(df_media["Spend"], errors="coerce")

    print("[3] Creating Google Sheets...")
    creds = get_credentials()
    drive_service = build("drive", "v3", credentials=creds)
    sheets_service = build("sheets", "v4", credentials=creds)

    source_id = create_sheet(drive_service, SOURCE_SHEET_NAME, force=args.force)
    print(f"Source: https://docs.google.com/spreadsheets/d/{source_id}")

    print("[4] Setting up tabs...")
    setup_tabs(
        sheets_service,
        source_id,
        [TAB_MEDIA, TAB_CAMPAIGN, TAB_REPORT_BUYER, TAB_REPORT_CAMP],
    )

    print("[5] Uploading data...")
    upload_dataframe(sheets_service, source_id, TAB_MEDIA, df_media)
    upload_dataframe(sheets_service, source_id, TAB_CAMPAIGN, df_campaign)

    print("[6] Adding reports...")
    add_report_formulas(sheets_service, source_id, top_n=25)

    print("[7] Creating target sheet...")
    target_id = create_sheet(drive_service, TARGET_SHEET_NAME, force=args.force)
    print(f"Target: https://docs.google.com/spreadsheets/d/{target_id}")

    print("[8] Copying data...")
    copy_sheet(sheets_service, source_id, TAB_MEDIA, target_id)
    copy_sheet(sheets_service, source_id, TAB_CAMPAIGN, target_id)
    copy_sheet(sheets_service, source_id, TAB_REPORT_BUYER, target_id)
    copy_sheet(sheets_service, source_id, TAB_REPORT_CAMP, target_id)

    print("[9] Creating charts in Target...")
    add_charts(
        sheets_service,
        target_id,
        buyers_count=df_media["Media Buyer"].nunique(),
        top_n=25,
    )

    print("\n✅ Done!")
    print(f"Source: https://docs.google.com/spreadsheets/d/{source_id}")
    print(f"Target: https://docs.google.com/spreadsheets/d/{target_id}")



if __name__ == "__main__":
    main()
