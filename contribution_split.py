# © flywire 2022, CC BY-SA
"""Split ETF Tax Contributions."""

import pandas as pd
from sys import argv


# py contribution_split.py ETF-Annual-Statement
FILENAME = argv[1]
df = pd.read_csv(FILENAME + ".csv")

cols = df.columns.tolist()
index_cols = cols[:3]

original_index = pd.MultiIndex.from_frame(df[index_cols])
data = (
    df.melt(id_vars=original_index.names, value_name="Amount")
    .set_index(index_cols)
    .loc[original_index]
    .reset_index(drop=False)
)

# add supporting columns
from_ = df.columns.tolist()[3:]
to_ = df.loc[df["Entity"] == "Account"].values.flatten().tolist()[3:]
data["Account"] = data["variable"].map(dict(zip(from_, to_))).fillna("")
to_ = df.loc[df["Entity"] == "Type"].values.flatten().tolist()[3:]
data["Type"] = data["variable"].map(dict(zip(from_, to_))).fillna("")

data["Amount"] = data["Amount"].apply(pd.to_numeric, errors="coerce")
data["Deposit"] = data.apply(
    lambda x: x["Amount"] if x["Type"] != "DR"
    else x["Amount"] * -1 if x["Amount"] != 0
    else x["Amount"], axis=1,
).round(decimals=2)

# # cleaning
data = data.drop(["variable", "Amount", "Type"], axis=1)
data = data[data["Description"].notna()]
data = data[data["Account"] != ""]
data = data[data["Deposit"].notna()]
print(data[data["Account"] == "Income:Distribution:Rounding"])
data = data[data["Deposit"].abs() != 0]

data.to_csv(FILENAME + '_split.csv', index=False, date_format="%d-%m-%Y")
