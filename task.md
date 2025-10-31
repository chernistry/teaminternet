## Introduction

You will extract data from an HTTP API, save it as CSV files, then upload those CSVs to Google Sheets and complete two follow-up tasks ("Data Transfer" and "Report Generation").

---

## Step 1 — Retrieve data from the API and convert to CSV

### Your job in Step 1:
Fetch each bin via the API, then convert each JSON array to a CSV file.

### How the API works

Read the JSONBin "Read Bins" API overview and samples here:  
https://jsonbin.io/api-reference/bins/read#code-samples

**Bin details** (use the latest route):
- Bin ID: `68ef72c243b1c97be9692f8c`
- Bin ID: `68ef7055ae596e708f14e54f`

**Endpoint pattern** (latest version, no metadata wrapper):
```
GET https://api.jsonbin.io/v3/b/<BIN_ID>/latest?meta=false
```

**Required headers** (bins are private):
```
X-Access-Key: $2a$10$3phmKfEbSPxJweZDflZKfusaZaJNM4P4p2OSbutkeNAaZY5rnR4zO
```

### Example request (cURL)

```bash
curl -s \
  -H 'X-Access-Key: $2a$10$3phmKfEbSPxJweZDflZKfusaZaJNM4P4p2OSbutkeNAaZY5rnR4zO' \
  'https://api.jsonbin.io/v3/b/68ef72c243b1c97be9692f8c/latest?meta=false'
```

### Example Request Response (with metadata wrapper)

If you omit `?meta=false` or don't set `X-Bin-Meta:false`, JSONBin returns a wrapper with record and metadata:

```json
{
  "record": [
    {
      "Platform": "facebook",
      "offer": "Immunity Booster PR",
      "country": "US",
      "adtitle": "how to get rid of ulcerative colitis",
      "Revenue": 121125.5455,
      "Leads": 225030,
      "Revenue Per Leads": 0.538263989,
      "top_10_keywords": "Velsipity Pills, Plaque Psoriasis Videos, ..."
    },
    {
      "Platform": "tiktok",
      "offer": "Dental Implants PR",
      "country": "US",
      "adtitle": "dental implants",
      "Revenue": 51008.33894,
      "Leads": 48645,
      "Revenue Per Leads": 1.048583389,
      "top_10_keywords": "Full Mouth Dental Implants For $99, ..."
    }
  ],
  "metadata": {
    "id": "68ef72c243b1c97be9692f8c",
    "private": true
  }
}
```

### Example Request Response (no metadata wrapper)

Use `?meta=false` to get the raw array:

```json
[
  {
    "Platform": "facebook",
    "offer": "Immunity Booster PR",
    "country": "US",
    "adtitle": "how to get rid of ulcerative colitis",
    "Revenue": 121125.5455,
    "Leads": 225030,
    "Revenue Per Leads": 0.538263989,
    "top_10_keywords": "Velsipity Pills, Plaque Psoriasis Videos, ..."
  },
  {
    "Platform": "tiktok",
    "offer": "Dental Implants PR",
    "country": "US",
    "adtitle": "dental implants",
    "Revenue": 51008.33894,
    "Leads": 48645,
    "Revenue Per Leads": 1.048583389,
    "top_10_keywords": "Full Mouth Dental Implants For $99, ..."
  }
]
```

### Second bin response example

```json
[
  {
    "Media Buyer": "John",
    "Country Code": "BR",
    "Campaign Name": "ex-br-a-hatr9999pt-1433065-j1505-tb-max-sc",
    "Revenue": "184.51",
    "Spend": "97.87"
  },
  {
    "Media Buyer": "Chris",
    "Country Code": "DE",
    "Campaign Name": "po-de-a-msta9999de-1432857-p1605-tb-max-sc",
    "Revenue": "64.57",
    "Spend": "53.14"
  }
]
```

---

## Step 2 — Google Sheets tasks

### Upload the CSVs

Upload the two CSV files you created to Google Sheets (two separate tabs/sheets is fine).

### Datasets (columns)

**Media Buyer Campaign Data**
- Columns: Media Buyer, Country Code, Campaign Name, Revenue, Spend

**Campaign Performance Data**
- Columns: Platform, Offer, Country, Ad Title, Revenue Prediction, Leads, Revenue Per Lead, Top 10 Keywords

---

## Tasks

### Task 1 — Data Transfer

- Transfer the data from Sheet 1 to another Google Sheet (Sheet 2).
- You can use Python, Google Apps Script, or any other method, but it must be something that can be easily updated in the future.
- Document your process and include any scripts or code used for the transfer.
- You are allowed to use ChatGPT or other resources to figure out the best method for this task.

### Task 2 — Report Generation

- Generate reports that provide meaningful insights to help media buyers optimize their campaigns and spending.
- Consider what metrics and visualizations would be most useful for media buyers.

**Example Report:**

Campaign Performance Summary: A report showing the total revenue, total spend, and average Revenue Per Lead for each media buyer. Identify the top-performing and underperforming campaigns based on these metrics.
