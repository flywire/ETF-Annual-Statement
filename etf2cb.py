# © flywire 2023, CC BY-SA
"""Get ETF Tax Contribution Splits from Annual Transaction Statement pdf."""

from dateutil import parser
import argparse
import csv
import datetime
import os
import re
import sys
import tabula
import tempfile
import time


def get_args():
    parser = argparse.ArgumentParser(
        description="""Extract ETF Annual Statement transaction component splits""",
        epilog="""Filenames with .csv extension are processed directly without pdf extract""",
    )
    parser.add_argument("filename", help="Provide filename to extract")
    parser.add_argument(
        "area", nargs="?", help="Table area reference required for pdf file"
    )
    return parser.parse_args()


def get_tabular_area(filename):
    """return nested list of tabular table areas."""
    area = []
    with open(filename) as csv_file:
        csv_list = list(csv.reader(csv_file))
        for r in csv_list[1:]:
            if r[0] != '':
                e = r[0]
                area.append([e])
                ie = len(area)-1
            if r[1] != '':
                p = r[1]
                area[ie].append([p])
                ip = len(area[ie])-1
                area[ie][ip].append([])
            area[ie][ip][1].append([int(r[c]) for c in range(2, 6)])
    return area


def csv_dictionary(filename):
    """return csv file as dictionary of dictionaries."""
    with open(filename, "r") as f:
        csv_list = list(csv.reader(f))
    (_, *header), *data = csv_list
    csv_dict = {}
    for row in data:
        key, *values = row
        csv_dict[key] = {key: value for key, value in zip(header, values)}
    return upper_dict_keys(csv_dict)


def upper_dict_keys(d):
    new_dict = dict((k.upper(), v) for k, v in d.items())
    return new_dict


def row_idx(list, str):
    """return row index list for lower case match of string and start of list."""
    _ = []
    for i, r in enumerate(list):
        if r[0][: len(str)].lower() == str.lower():
            _.append([i, r])
    return _


def txn_split(key, account, amount, balance):
    """form transaction split list and balance"""
    # Entity,Date,Description,Account,Deposit
    # balance as cents
    balance += int(amount.replace(".", ""))
    row = key.copy()
    row.append(account)
    row.append(amount)
    return row, balance


def part_a(acc_dict, ats_list, idx_b, key, balance, writer):
    """form transaction splits and balance - Part A"""
    # Get amount and label columns
    for i, r in enumerate(ats_list[4]):
        if "amount" in r.lower():
            c = i
        if "label" in r.lower():
            label_c = i
    for r in ats_list[5:idx_b]:
        if (
            r[c]
            and r[c] != "$0.00"
            and re.compile(r"^\d{2}\D$").search(r[label_c]) != None
        ):
            typ = acc_dict.get(r[label_c]).get("Type")
            amount = r[c].replace(",", "")[1:]
            if typ == "DB":
                amount = "-" + amount
            label = r[label_c]
            account = acc_dict.get(label).get("Account")
            if label == "18A":
                ncg = amount
            elif label == "18H":
                amount = "-" + amount
                amount = str(
                    (int(amount.replace(".", "")) - int(ncg.replace(".", ""))) / 100
                )
                account = "Income:Distribution:18H:GCTGrossUp"
            if label != "20M":
                row, balance = txn_split(key, account, amount, balance)
                _ = writer.writerow(row)
    return balance


def dictionary_key_fuzzy_match(dict, search):
    """return list of keys for search."""
    return [k for k in [*dict] if k.lower() in search.lower()]


def part_b(acc_dict, ats_list, idx_b, key, balance, writer):
    """form transaction splits and balance - Part B"""
    # Skip to non-tax items
    skip = True
    for i, r in enumerate(ats_list[idx_b:]):
        if skip:
            if "Non-assessable Amounts".upper() in r[0].upper():
                skip = False
        else:
            for c in [1, 3]:
                if (
                    r[c]
                    and r[c] != "$0.00"
                    and re.compile(r"^\$?[0-9,]*\.[0-9]{2}$").search(r[c]) != None
                ):
                    # Write non-zero amounts
                    # The tax-acc key (label) is a subset of r[c] ie ats_list[0]
                    label_list = dictionary_key_fuzzy_match(acc_dict, r[0])
                    if not len(label_list):
                        print(
                            "Label: ",
                            r[0],
                            "does not occur in Tax Accounts, processing failed.",
                        )
                        # raise exception
                        quit()
                    elif len(label_list) > 1:
                        # multiple matches so use exact match
                        label_list = acc_dict.get(r[0])
                        break
                        # raise exception
                        quit()
                        print(
                            r[0], "in multiple Tax Accounts labels, processing failed."
                        )
                    label = label_list[0]
                    typ = acc_dict.get(label.upper()).get("Type")
                    amount = r[c].replace(",", "")[1:]
                    if typ.lower() == "skip".lower():
                        break
                    if typ == "DB":
                        amount = "-" + amount
                    account = acc_dict.get(label).get("Account")
                    row, balance = txn_split(key, account, amount, balance)
                    _ = writer.writerow(row)
                else:
                    pass
                    # print('Skip', c, r)
    return balance


def close_txn(acc_dict, key, balance, writer):
    if balance != 0:
        account = acc_dict.get("Rounding".upper()).get("Account")
        amount = str(-1 * balance / 100)
        row, balance = txn_split(key, account, amount, balance)
        _ = writer.writerow(row)
    return


def main():
    try:
        args = get_args()
        if args.filename[-4:].lower() == ".csv":
            cdf = args.filename
        elif args.area is None:
            # parser.error('area argument required if no .csv filename extension')
            raise TypeError("area argument required if no .csv filename extension")
        else:
            # Get table from pdf
            area = get_tabular_area('tabula-area.csv')
            # Catch exception when tabula_area not found
            pdf = (
                args.filename
                if args.filename[-4:].lower() == ".pdf"
                else args.filename + ".pdf"
            )
            tmpf = "tempfile.txt"
            cdf = pdf[:-4] + ".csv"
            # Get pdf area from tabula_area.py
            idx_area = [i[0].lower() for i in area].index(args.area.lower())
            for j in range(1, len(area[idx_area])):
                tabula.convert_into(
                    pdf, tmpf, pages=area[idx_area][j][0], area=area[idx_area][j][1]
                )
                with open(tmpf, "r") as sfile:
                    mode = "w" if j == 1 else "a"
                    with open(cdf, mode) as tfile:
                        tfile.write(sfile.read())
            os.remove(tmpf)
        csvs = cdf[:-4] + "_split.csv"
        acc_dict = csv_dictionary("tax-acc.csv")
        # Catch exception when acc_dict not found

        # Process annual tax statement
        # To a list
        with open(cdf, newline="") as ifile:
            ats_list = list(csv.reader(ifile))
        # Get statement structure
        idx_b, _ = row_idx(ats_list, "Part B")[0]
        # # Validate
        # idx_item = row_idx(ats_list, "Item")
        # if idx_item[0][0] != 4:
        #     print("Part A header - Invalid")
        # if idx_item[1][0] != idx_b + 1:
        #     print("Part B header - Invalid")
        # Row key
        key = []
        key.append(re.sub(r"\s+", '', ats_list[1][0])) # remove whitespace
        key.append(parser.parse(ats_list[2][0]).date().strftime("%d/%m/%Y"))
        key.append(ats_list[0][0])
        # Do parts
        with open(csvs, "w", newline="") as ofile:
            writer = csv.writer(ofile, delimiter=",", quotechar='"')
            balance = 0
            balance = part_a(acc_dict, ats_list, idx_b, key, balance, writer)
            balance = part_b(acc_dict, ats_list, idx_b, key, balance, writer)
            _ = close_txn(acc_dict, key, balance, writer)
        print("done.")
    except IndexError:
        print("Unknown statement structure, processing failed.")
        # _ = [print(r[0]) for r in ats_list]
    except AttributeError:
        # print(r)
        print(
            "Line",
            sys.exc_info()[-1].tb_lineno,
            "- Item label does not occur in Tax Accounts, processing failed.",
        )
        # _ = [print(r[0]) for r in ats_list]


if __name__ == "__main__":
    main()
