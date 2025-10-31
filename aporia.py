#!/usr/bin/env python3
"""Aporia Test - Python automation solution"""

import json
import requests
import pandas as pd
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import subprocess

# Config
PROJECT_ID = "teaminternet"
FOLDER_ID = "17Qa_v6D65-_HANHbRnAyYf82JxYhsQde"
JSONBIN_KEY = "$2a$10$3phmKfEbSPxJweZDflZKfusaZaJNM4P4p2OSbutkeNAaZY5rnR4zO"
BIN_CAMPAIGN = "68ef72c243b1c97be9692f8c"
BIN_MEDIA = "68ef7055ae596e708f14e54f"

def get_credentials():
    """Get credentials from gcloud"""
    token = subprocess.check_output(['gcloud', 'auth', 'print-access-token']).decode().strip()
    return Credentials(token=token)

def fetch_jsonbin(bin_id):
    """Fetch data from JSONBin"""
    url = f"https://api.jsonbin.io/v3/b/{bin_id}/latest?meta=false"
    headers = {"X-Access-Key": JSONBIN_KEY}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()

def create_sheet(service, name):
    """Create spreadsheet in folder"""
    body = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.spreadsheet',
        'parents': [FOLDER_ID]
    }
    file = service.files().create(body=body, fields='id').execute()
    return file['id']

def setup_tabs(sheets_service, spreadsheet_id, tab_names):
    """Rename first tab and add others"""
    requests = [
        {'updateSheetProperties': {'properties': {'sheetId': 0, 'title': tab_names[0]}, 'fields': 'title'}}
    ]
    for name in tab_names[1:]:
        requests.append({'addSheet': {'properties': {'title': name}}})
    
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={'requests': requests}
    ).execute()

def upload_dataframe(sheets_service, spreadsheet_id, sheet_name, df):
    """Upload DataFrame to sheet"""
    values = [df.columns.tolist()] + df.values.tolist()
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption='USER_ENTERED',
        body={'values': values}
    ).execute()

def add_report_formulas(sheets_service, spreadsheet_id, buyers_count: int):
    """Add QUERY formulas to Report tab"""
    # Get sheet IDs
    meta = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    report_id = next(s['properties']['sheetId'] for s in meta['sheets'] if s['properties']['title'] == 'Report')
    
    # 1) Header and Media Buyer Summary at top
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={'requests': [{
            'updateCells': {
                'range': {'sheetId': report_id, 'startRowIndex': 0, 'startColumnIndex': 0},
                'rows': [
                    {'values': [{'userEnteredValue': {'stringValue': 'Media Buyer Summary (Revenue, Spend, ROI)'}}]},
                    {'values': []},
                    {'values': [{'userEnteredValue': {'formulaValue':
                        '=QUERY(Raw_MediaBuyer!A2:E, "select Col1, sum(Col4), sum(Col5) group by Col1 order by sum(Col4) desc", 0)'
                    }}]}
                ],
                'fields': 'userEnteredValue'
            }
        }]}
    ).execute()
    
    # 2) ROI header + first formula (will be auto-filled below)
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={'requests': [{
            'updateCells': {
                'range': {'sheetId': report_id, 'startRowIndex': 2, 'startColumnIndex': 3},
                'rows': [
                    {'values': [{'userEnteredValue': {'stringValue': 'ROI'}}]},
                    {'values': [{'userEnteredValue': {'formulaValue': '=IFERROR((B4-C4)/C4,)'}}]}
                ],
                'fields': 'userEnteredValue'
            }
        }]}
    ).execute()
    
    # 3) Campaign Performance block far below to avoid spill collision
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={'requests': [{
            'updateCells': {
                'range': {'sheetId': report_id, 'startRowIndex': 24, 'startColumnIndex': 0},  # Row 25
                'rows': [
                    {'values': [{'userEnteredValue': {'stringValue': 'Campaign Performance (Revenue, Leads, RPL)'}}]},
                    {'values': []},
                    {'values': [{'userEnteredValue': {'formulaValue':
                        '=QUERY(Raw_Campaign!A2:H, "select Col1, Col2, Col3, sum(Col5), sum(Col6), sum(Col5)/sum(Col6) group by Col1, Col2, Col3 order by sum(Col5) desc", 0)'
                    }}]}
                ],
                'fields': 'userEnteredValue'
            }
        }]}
    ).execute()

    # 4) Copy ROI formula down exactly to match buyers_count
    if buyers_count and buyers_count > 1:
        dest_end = 3 + buyers_count  # zero-based exclusive end (row 4..row 3+count)
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [{
                'copyPaste': {
                    'source': {
                        'sheetId': report_id,
                        'startRowIndex': 3, 'endRowIndex': 4, 'startColumnIndex': 3, 'endColumnIndex': 4
                    },
                    'destination': {
                        'sheetId': report_id,
                        'startRowIndex': 4, 'endRowIndex': dest_end, 'startColumnIndex': 3, 'endColumnIndex': 4
                    },
                    'pasteType': 'PASTE_FORMULA'
                }
            }]}
        ).execute()
    
    # AutoFill ROI formula down a generous range; IFERROR prevents noise on empty rows
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={'requests': [{
            'autoFill': {
                'useAlternateSeries': False,
                'sourceAndDestination': {
                    'source': {
                        'sheetId': report_id,
                        'startRowIndex': 3, 'endRowIndex': 4, 'startColumnIndex': 3, 'endColumnIndex': 4
                    },
                    'dimension': 'COLUMNS',
                    'fillLength': 200
                }
            }
        }]}
    ).execute()

def add_charts(sheets_service, spreadsheet_id):
    """Add charts to Report tab"""
    meta = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    report_id = next(s['properties']['sheetId'] for s in meta['sheets'] if s['properties']['title'] == 'Report')
    
    requests = [
        {
            'addChart': {
                'chart': {
                    'spec': {
                        'title': 'Revenue vs Spend by Media Buyer',
                        'basicChart': {
                            'chartType': 'COLUMN',
                            'legendPosition': 'BOTTOM_LEGEND',
                            'domains': [{'domain': {'sourceRange': {'sources': [{'sheetId': report_id, 'startRowIndex': 2, 'startColumnIndex': 0, 'endColumnIndex': 1}]}}}],
                            'series': [
                                {'series': {'sourceRange': {'sources': [{'sheetId': report_id, 'startRowIndex': 2, 'startColumnIndex': 1, 'endColumnIndex': 2}]}}},
                                {'series': {'sourceRange': {'sources': [{'sheetId': report_id, 'startRowIndex': 2, 'startColumnIndex': 2, 'endColumnIndex': 3}]}}},
                                {'series': {'sourceRange': {'sources': [{'sheetId': report_id, 'startRowIndex': 2, 'startColumnIndex': 3, 'endColumnIndex': 4}]}}, 'targetAxis': 'RIGHT_AXIS'}
                            ],
                            'headerCount': 1
                        }
                    },
                    'position': {'overlayPosition': {'anchorCell': {'sheetId': report_id, 'rowIndex': 0, 'columnIndex': 7}}}
                }
            }
        },
        {
            'addChart': {
                'chart': {
                    'spec': {
                        'title': 'Top Platforms/Offers by Revenue',
                        'basicChart': {
                            'chartType': 'COLUMN',
                            'legendPosition': 'BOTTOM_LEGEND',
                            'domains': [{'domain': {'sourceRange': {'sources': [{'sheetId': report_id, 'startRowIndex': 6, 'startColumnIndex': 0, 'endColumnIndex': 1}]}}}],
                            'series': [
                                {'series': {'sourceRange': {'sources': [{'sheetId': report_id, 'startRowIndex': 6, 'startColumnIndex': 3, 'endColumnIndex': 4}]}}},
                                {'series': {'sourceRange': {'sources': [{'sheetId': report_id, 'startRowIndex': 6, 'startColumnIndex': 4, 'endColumnIndex': 5}]}}},
                                {'series': {'sourceRange': {'sources': [{'sheetId': report_id, 'startRowIndex': 6, 'startColumnIndex': 5, 'endColumnIndex': 6}]}}, 'targetAxis': 'RIGHT_AXIS'}
                            ],
                            'headerCount': 1
                        }
                    },
                    'position': {'overlayPosition': {'anchorCell': {'sheetId': report_id, 'rowIndex': 18, 'columnIndex': 7}}}
                }
            }
        }
    ]
    
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={'requests': requests}
    ).execute()

def copy_sheet(sheets_service, source_id, sheet_name, target_id):
    """Copy sheet to target spreadsheet"""
    meta = sheets_service.spreadsheets().get(spreadsheetId=source_id).execute()
    sheet_id = next(s['properties']['sheetId'] for s in meta['sheets'] if s['properties']['title'] == sheet_name)
    
    result = sheets_service.spreadsheets().sheets().copyTo(
        spreadsheetId=source_id,
        sheetId=sheet_id,
        body={'destinationSpreadsheetId': target_id}
    ).execute()
    
    # Rename copied sheet
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=target_id,
        body={'requests': [{'updateSheetProperties': {'properties': {'sheetId': result['sheetId'], 'title': sheet_name}, 'fields': 'title'}}]}
    ).execute()

def main():
    print("[1] Fetching data from JSONBin...")
    campaign_data = fetch_jsonbin(BIN_CAMPAIGN)
    media_data = fetch_jsonbin(BIN_MEDIA)
    
    print("[2] Converting to DataFrames...")
    df_campaign = pd.DataFrame(campaign_data)
    df_campaign = df_campaign.rename(columns={
        'Platform': 'Platform',
        'offer': 'Offer',
        'country': 'Country',
        'adtitle': 'Ad Title',
        'Revenue': 'Revenue Prediction',
        'Leads': 'Leads',
        'Revenue Per Leads': 'Revenue Per Lead',
        'top_10_keywords': 'Top 10 Keywords'
    })
    
    df_media = pd.DataFrame(media_data)
    df_media['Revenue'] = pd.to_numeric(df_media['Revenue'], errors='coerce')
    df_media['Spend'] = pd.to_numeric(df_media['Spend'], errors='coerce')
    
    print("[3] Creating Google Sheets...")
    creds = get_credentials()
    drive_service = build('drive', 'v3', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)
    
    source_id = create_sheet(drive_service, "Aporia Test")
    print(f"Source: https://docs.google.com/spreadsheets/d/{source_id}")
    
    print("[4] Setting up tabs...")
    setup_tabs(sheets_service, source_id, ['Raw_MediaBuyer', 'Raw_Campaign', 'Report'])
    
    print("[5] Uploading data...")
    upload_dataframe(sheets_service, source_id, 'Raw_MediaBuyer', df_media)
    upload_dataframe(sheets_service, source_id, 'Raw_Campaign', df_campaign)
    
    print("[6] Adding reports...")
    add_report_formulas(sheets_service, source_id, df_media['Media Buyer'].nunique())
    add_charts(sheets_service, source_id)
    
    print("[7] Creating target sheet...")
    target_id = create_sheet(drive_service, "Aporia Target")
    print(f"Target: https://docs.google.com/spreadsheets/d/{target_id}")
    
    print("[8] Copying data...")
    copy_sheet(sheets_service, source_id, 'Raw_MediaBuyer', target_id)
    copy_sheet(sheets_service, source_id, 'Raw_Campaign', target_id)
    copy_sheet(sheets_service, source_id, 'Report', target_id)
    
    print("\n✅ Done!")
    print(f"Source: https://docs.google.com/spreadsheets/d/{source_id}")
    print(f"Target: https://docs.google.com/spreadsheets/d/{target_id}")

if __name__ == '__main__':
    main()
