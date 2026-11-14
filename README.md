# etf2cb

Convert Australian ETF Annual Tax Statements (PDF or extracted text) into split transaction CSV files ready to import into accounting programs (such as GnuCash).

## Features
* **Direct Text Extraction:** Extracts data directly from PDF text without manual coordinate mapping.
* **Multi-Registry Support:** Parsers currently support pdf/txt statements from:
  * Computershare
  * Link Market Services / MUFG Corporate Markets
  * Automic
  * Magellan
  * One Registry Services
* **Flexible Input Formats:** Accepts `.pdf`, plain-text `.txt` dumps, or normalized `.csv` files.
* **Customisable Account Mapping:** Maps ATO tax labels and AMIT cost base adjustments to your chart of accounts via `tax-acc.csv`.

## Installation

### Option 1: Standalone Windows Executable
Download `etf2cb.exe` and `tax-acc.csv` from the [Releases](../../releases) page and place them in the same directory (or in your PDF statements folder).

### Option 2: Run from Source with `uv`
Install [uv](https://docs.astral.sh/uv/), create a virtual environment, and install the dependencies:

```bash
uv venv
uv pip install -r requirements.txt
```

Check the installed version:
```bash
uv run etf2cb.py --version
```

## Usage

### Single Statement
Process a single PDF or text dump (produces `<filename>_split.csv`):

```bash
# Using the compiled executable
etf2cb.exe "VAS-annual-tax-statement.pdf"

# Or from source with uv
uv run etf2cb.py "VAS-annual-tax-statement.pdf"
```

### Batch Processing All Statements in a Folder
Individual `*_split.csv` files are generated without a header row so they can be merged cleanly into a single `all_splits.csv` file.

**Windows Command Prompt (CMD):**
```cmd
del *_split.csv all_splits.csv 2>nul
for %f in (*.pdf) do etf2cb.exe "%f"
echo Entity,Date,Description,Account,Deposit > all_splits.csv & type *_split.csv >> all_splits.csv
```

## Sample Output (`all_splits.csv`)

Sample transaction showing splits:

```csv
Entity,Date,Description,Account,Deposit
X0123456789,30/06/2018,VAS,Income:Distribution:13U,-3606.42
X0123456789,30/06/2018,VAS,Income:Distribution:13C,-22870.71
X0123456789,30/06/2018,VAS,Income:Distribution:13Q,7069.35
X0123456789,30/06/2018,VAS,Income:Distribution:18H:18A,-1568.43
X0123456789,30/06/2018,VAS,Income:Distribution:18H:GCTGrossUp,-1567.05
X0123456789,30/06/2018,VAS,Income:Distribution:20E/20M,-463.54
X0123456789,30/06/2018,VAS,Income:Distribution:20O,15.64
X0123456789,30/06/2018,VAS,Asset:Shares:CostBase,-62.21
X0123456789,30/06/2018,VAS,Income:Distribution:Attributed,23053.38
X0123456789,30/06/2018,VAS,Income:Distribution:Rounding,-0.01
```

## Recommended Data Validation

Before using the data, open `all_splits.csv` in a spreadsheet and create a Pivot Table to reconcile against your statements and check your ATO pre-fill report and cashbook:

* **Filters:** `Entity`, `Date`
* **Rows:** `Account`
* **Columns:** `Description`
* **Values:** `Sum of Deposit`

### What to Check
1. **Zero Net Balance:** Confirm the **Grand Total** for every ETF column (and overall) equals `0.00`.
2. **Rounding Check:** Inspect the `Income:Distribution:Rounding` row—values should only be a few cents (`±0.01`–`0.02`). A larger figure indicates an unmapped or skipped component on that statement.
3. **Match Tax Totals:** Compare the tax code row totals (`10L`, `13U`, `13C`, `13Q`, `18A`, `18H`, `20E`, and `20O`) directly against each ETF's Annual Tax Statement and your myTax / ATO pre-fill summary.
4. **Verify Cash Distributions:** Confirm `Income:Distribution:Attributed` matches the total net cash distributions received in your bank or broker cash account for the financial year (and adjust for any distributions paid across the 30 June financial year boundary).

## Importing into GnuCash

1. Open GnuCash and select **File → Import → Import Transactions from CSV**.
2. Select `all_splits.csv` (or an individual `*_split.csv`).
3. Configure the import settings:
   * **Encoding:** `UTF-8`
   * **Separator:** `Comma`
   * **Date Format:** `d-m-y`
   * **Multi-split:** Checked
   * **Leading lines to skip:** `1` for `all_splits.csv` (or `0` for a headerless `*_split.csv`)
4. Map the columns:
   * `Entity` → **Notes** (or **Memo** / **Num**, used to separate holdings/HINs)
   * `Date` → **Date**
   * `Description` → **Description**
   * `Account` → **Account**
   * `Deposit` → **Deposit**
5. Review the account matches and complete the import.

## Customising Account Mappings (`tax-acc.csv`)

Edit `tax-acc.csv` to match your own chart of accounts:
* **`Label`:** ATO tax return label (`13U`, `18A`, etc.) or statement component name.
* **`Type`:** `DB` (negates positive amounts for income/cost-base reductions), `CR` (keeps positive sign for offsets/cash/cost-base increases), or `skip` (ignores subtotal lines).
* **`Account`:** Target account path in your accounting software.

## Building Releases (Maintainers)

Releases are built manually via GitHub Actions (`.github/workflows/release.yml`):
1. Go to **Actions → Manual Date-Based Release → Run workflow**.
2. Leave `release_date` blank to use today's date (`yyyy.mm.dd` in Australia/Sydney time) or enter a custom date.
3. The workflow strips `-dev`, compiles `etf2cb.exe` via PyInstaller, creates tag `v<yyyy.mm.dd>` with `etf2cb.exe`, `tax-acc.csv`, and `etf2cb-<version>-windows.zip`, and bumps `_version.py` in the repository to `<yyyy.mm.dd>-dev`.
4. Same-day duplicate releases are blocked by default unless the **overwrite** checkbox is ticked.

## License

This project is licensed under the terms of the [GNU General Public License v3.0](https://gnu.org) (or any later version).
