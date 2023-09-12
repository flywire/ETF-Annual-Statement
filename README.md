# ETF-Annual-Statement

Reporting for multiple Australian ETF Annual Tax Statements.

## Objectives

* Read the data from the Australian ETF Annual Tax Statements and reformat it as
a split transaction to load into a cashbook (eg GnuCash).
* If the pdf format is not directly supported the intermediate csv file can be
reworked using the example file as a template before loading the csv file.

## Installation

Windows users should look for `etf2cb.exe` and download it if it is available
then skip to the next section.

---

Python software can optionally be installed in a virtual environment to
eliminate system conflicts as described
[here](https://docs.python.org/3/library/venv.html).
eg in the desired folder for Windows:

```
python -m venv ./venv/etf2cb
.\venv\etf2cb\scripts\activate
cd .\venv\etf2cb
```
Use `deactivate` to return to the normal system.

```
pip install git+https://github.com/flywire/ETF-Annual-Statement.git@main
```

### Troubleshooting

This package uses [tabula-py](https://github.com/chezou/tabula-py) under the
hood, which itself is a wrapper for
[tabula-java](https://github.com/tabulapdf/tabula-java).

Windows & Linux users will need a copy of Java installed. You can download
Java [here](https://www.java.com/download/).

## Usage

Start a command prompt.

If you downloaded `etf2cb.exe` it is run without the `python` prefix or `.py`
extension, but otherwise it is the same.

Alternatively,

```
python etf2cb.py -h
usage: etf2cb.py [-h] filename [area]

Extract ETF Annual Statement transaction component splits

positional arguments:
  filename    Provide filename to extract
  area        Table area reference required for pdf file

options:
  -h, --help  show this help message and exit

Filenames with .csv extension are processed directly without pdf extract
```

Many things can fail with this automated process so users should validate the
output manually.
Firstly, check the total of all deposit amounts is zero.

## Customising

Amounts will be extracted from the pdf using the area reference unless run on
a `.csv` file.

1. `tabula-area.csv` must be specified to extract data from pdf
1. `tax-acc.csv` must be configured for each label

The `tabula-area.csv` file in the distribution is user-configurable.

Tax account configuration is required in a user-configurable `tax-acc.csv`
file containing the following fields:

1. `Label` - first part uses tax codes, second part uses strings in pdf labels
1. `Description` - details are optional
1. `Type` - 'CR' or 'DB' account
1. `Account` - users cashbook chart of account code

## Sample Output

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
X0123456789,30/06/2018,VAS,Income:Distribution,23053.38
X0123456789,30/06/2018,VAS,Income:Distribution:Rounding,-0.01
```

There are many ways to accumulate the splits for all ETFs by entity and year.

In GnuCash use:
1. File, Import, Import Transactions from csv,
1. Next, Select ETF-Annual-Statement_split.csv, Next,
1. Leading lines to skip: 1, Date format: d-m-y, Select Multi-split
1. Select Date, Description, Account, Deposit, Next
1. Map Account ID to Account Name, Next, Next, Close
