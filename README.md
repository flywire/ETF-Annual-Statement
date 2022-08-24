# ETF-Annual-Statement

Files to support a process to form accounting splits from Australian ETF
Annual Statements for loading into GnuCash. The process creates a pivot
table, determines deposits based on CR/DB lables and forms a multisplit csv
file.

## Usage

ETF statement values like the sample VAS-annual-tax-statement-2018.png is
loaded into ETF-Annual-Statement.xlsx and saved as a csv file. This could be
automated.

Run `py contribution_split.py ETF-Annual-Statement` to convert the
ETF-Annual-Statement.csv csv file into a csv file that can be loaded into
GnuCash. For each Entity/Date/Description record the rounding Account is
printed to the console as a check for a balanced transaction.

In GnuCash use:
1. File, Import, Import Transactions from csv,
1. Next, Select ETF-Annual-Statement_split.csv, Next,
1. Leading lines to skip: 1, Date format: d-m-y, Select Multisplit
1. Select Date, Description, Account, Deposit, Next
1. Map Account ID to Account Name, Next, Next, Close

## Customising

The first three columns contain the index rows and subsequent columns data.
Data columns and supporting rows can be added and deleted as required but CR
and DB totals should be adjusted for Rounding check.

## Sample Output

```csv
Entity,Date,Description,Account,Deposit
Super,30/06/2018,VAS,Income:Distribution:13U,-3606.42
Super,30/06/2018,VAS,Income:Distribution:13C,-22870.71
Super,30/06/2018,VAS,Income:Distribution:13Q,7069.35
Super,30/06/2018,VAS,Income:Distribution:18H:18A,-1568.43
Super,30/06/2018,VAS,Income:Distribution:18H:GCTGrossUp,-1567.05
Super,30/06/2018,VAS,Income:Distribution:20E/20M,-463.54
Super,30/06/2018,VAS,Income:Distribution:20O,15.64
Super,30/06/2018,VAS,Income:Distribution,23053.38
Super,30/06/2018,VAS,Asset:Shares:CostBase,-62.21
Super,30/06/2018,VAS,Income:Distribution:Rounding,-0.01
```
