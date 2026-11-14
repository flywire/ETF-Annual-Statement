# Copyright (C) 2023-2026 flywire
# SPDX-License-Identifier: GPL-3.0-or-later
"""Get ETF Tax Contribution Splits from Annual Transaction Statement pdf."""

from dateutil import parser
import argparse
import csv
import os
import re
import sys
import pdfplumber

try:
    from _version import __version__
except ImportError:
    __version__ = "dev"


def get_args():
    p = argparse.ArgumentParser(
        description="""Extract ETF Annual Statement transaction component splits""",
        epilog="""Filenames with .csv or .txt extension are processed directly without pdf extract""",
    )
    p.add_argument("filename", help="Provide filename to extract")
    p.add_argument(
        "area", nargs="?", help="Optional (unused with text-based PDF extraction)"
    )
    p.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return p.parse_args()


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
    return dict((k.upper(), v) for k, v in d.items())


def row_idx(lst, s):
    """return row index list for lower case match of string and start of list."""
    return [[i, r] for i, r in enumerate(lst) if r and r[0][: len(s)].lower() == s.lower()]


def txn_split(key, account, amount, balance):
    """form transaction split list and balance"""
    # Entity,Date,Description,Account,Deposit
    # balance as cents
    balance += int(amount.replace(".", ""))
    row = key.copy()
    row.append(account)
    row.append(amount)
    return row, balance


def _norm_amt(amt):
    """Convert accounting brackets (10.00) to -10.00 and strip $ and commas."""
    s = amt.replace("$", "").replace(",", "").strip()
    if s.startswith("(") and s.endswith(")"):
        return "-" + s[1:-1]
    return s


def _apply_sign(raw_amt, typ):
    """Apply DB/CR sign convention to a normalised numeric string."""
    val = _norm_amt(raw_amt)
    if typ == "DB":
        return val[1:] if val.startswith("-") else "-" + val
    return val


def detect_provider(full_text):
    """Identify the registry format from the PDF text."""
    flat = "".join(full_text.split()).lower()
    if "computershare" in flat:
        return "computershare"
    if any(r in flat for r in ("linkmarketservices", "mufgcorporatemarkets", "mpms.mufg.com")):
        return "link"
    if "automic" in flat:
        return "automic"
    if "magellan" in flat:
        return "magellan"
    if "oneregistryservices" in flat:
        return "oneregistry"
    return "unknown"


def extract_entity(lines):
    """Extract HIN, SRN, Holder Number, Account Number, or Reference No. safely."""
    label_re = re.compile(
        r"\b(?:Holder\s+Identification\s+Number|Securityholder\s+Reference\s+Number|"
        r"Holder\s+Number|Account\s+Number|Investor\s+Number|"
        r"HIN|SRN|Reference\s+No\.?)\b",
        re.IGNORECASE,
    )
    id_re = re.compile(r"^(?:[A-Z]{0,2}\s*[\d*]{4,12}|HIN\s+WITHHELD)$", re.IGNORECASE)

    for i, line in enumerate(lines):
        m_inline = re.search(
            r"\b(?:HIN|SRN|Holder\s+Number|Account\s+Number|Investor\s+Number|Reference\s+No\.?)\s*:?\s*"
            r"([A-Z]{0,2}\s*[\d*]{4,12}|HIN\s+WITHHELD)\b",
            line,
            re.IGNORECASE,
        )
        if m_inline:
            val = re.sub(r"\s+", "", m_inline.group(1)).upper()
            return "WITHHELD" if "WITHHELD" in val else val

        if label_re.search(line):
            for offset in range(1, 4):
                if i + offset < len(lines):
                    candidate = lines[i + offset].strip()
                    if id_re.match(candidate):
                        val = re.sub(r"\s+", "", candidate).upper()
                        return "WITHHELD" if "WITHHELD" in val else val

    for line in lines:
        m_standalone = re.search(r"(?<![A-Z0-9])([XI]\s*[\d*]{8,11})(?![\d*])", line)
        if m_standalone:
            return re.sub(r"\s+", "", m_standalone.group(1)).upper()

    return "UNKNOWN"


def extract_ticker(lines, provider):
    """Extract ASX / Fund ticker code."""
    for i, line in enumerate(lines):
        m_code = re.search(r"\b(?:ASX\s+Code|Fund\s+Code)\s*:?\s*([A-Z0-9]{2,8})\b", line)
        if m_code:
            return m_code.group(1)
        m_cs = re.search(r"^T\s+\d+\s+000\s+([A-Z0-9]{2,6})\b", line)
        if m_cs:
            return m_cs.group(1)

    if provider == "oneregistry":
        for i, line in enumerate(lines):
            if "AMIT Member Annual Statement" in line and i > 0:
                words = re.findall(r"[A-Za-z]+", lines[i - 1])
                stop = {"fund", "trust", "series", "the", "of", "and", "pty", "ltd"}
                letters = "".join(w[0].upper() for w in words if w.lower() not in stop)
                if len(letters) >= 2:
                    return letters[:6]

    return "UNKNOWN"


def extract_fy_date(lines):
    """Extract financial year end date string."""
    for line in lines:
        m_date = re.search(
            r"YEAR\s+ENDED\s*:?\s*(\d{1,2}[-\s]+[A-Za-z]+[-\s]+\d{2,4})",
            line,
            re.IGNORECASE,
        )
        if m_date:
            return m_date.group(1)
    return ""


def _parse_computershare(lines, amount_re):
    """Parse Computershare (Vanguard / iShares) statements."""
    part_a_rows = []
    part_b_rows = []
    section = None

    for line in lines:
        if re.match(r"^PART\s+A\b", line, re.IGNORECASE):
            section = "A"
            continue
        if re.match(r"^PART\s+B\b", line, re.IGNORECASE):
            section = "B"
            continue
        if line.startswith("PLEASE RETAIN"):
            break

        if section == "A":
            m = re.match(r"^(.*?)\s+(\d{2}[A-Z])\*?(?:\s+(\(?-?\$[\d,]+\.\d{2}\)?))?$", line)
            if m:
                part_a_rows.append([m.group(1).strip(), m.group(2), _norm_amt(m.group(3) or "")])
        elif section == "B":
            amounts = amount_re.findall(line)
            label = re.sub(r"\s+\d{1,2}$", "", amount_re.split(line, maxsplit=1)[0].strip())
            if amounts:
                part_b_rows.append([label, _norm_amt(amounts[-1]), "", ""])
            elif label and not amount_re.match(line):
                part_b_rows.append([label, "", "", ""])

    if part_a_rows and not any(r[2] for r in part_a_rows):
        figure_lines = [
            amount_re.findall(l)
            for l in lines
            if re.fullmatch(r"(?:\(?-?\$[\d,]+\.\d{2}\)?\s*)+", l)
        ]
        for idx, r in enumerate(part_a_rows):
            if idx < len(figure_lines):
                r[2] = _norm_amt(figure_lines[idx][-1])
        b_figs = figure_lines[len(part_a_rows):]
        headings = {
            "australian income",
            "capital gains",
            "foreign income",
            "other non-assessable amounts",
            "less:",
        }
        aligned_b = []
        for label_row, figs in zip(
            [r[0] for r in part_b_rows if r[0].lower() not in headings], b_figs
        ):
            aligned_b.append([label_row, _norm_amt(figs[-1]), "", ""])
        part_b_rows = aligned_b

    return part_a_rows, part_b_rows


def _parse_link_mufg(lines, amount_re):
    """Parse Link Market Services / MUFG Corporate Markets statements."""
    in_components = False
    in_tax_offsets = False
    part_a_rows = []
    part_b_rows = []
    pending_label = ""
    skip_prefixes = ("total ", "less: gross-ups", "less: attributed amounts not paid")

    for line in lines:
        if re.search(r"Components?\s+of\s+(?:attribution|distribution)", line, re.IGNORECASE):
            in_components = True
            in_tax_offsets = False
            pending_label = ""
            continue
        if re.match(r"^(?:Part\s+F\b|Payment\s+summary|Tax\s+Guide\b)", line, re.IGNORECASE):
            break

        if not in_components:
            m_full = re.match(r"^(.*?)\s+(\(?-?\$[\d,]+\.\d{2}\)?)\s+(\d{2}[A-Z])$", line)
            if m_full:
                lbl = (pending_label + " " + m_full.group(1)).strip()
                part_a_rows.append([lbl, m_full.group(3), _norm_amt(m_full.group(2))])
                pending_label = ""
                continue

            m_tail = re.match(r"^(\(?-?\$[\d,]+\.\d{2}\)?)\s+(\d{2}[A-Z])$", line)
            if m_tail and pending_label:
                part_a_rows.append([pending_label.strip(), m_tail.group(2), _norm_amt(m_tail.group(1))])
                pending_label = ""
                continue

            if not amount_re.search(line) and not re.match(
                r"^(?:Part\s+[AB]|Summary|Tax\s+return|Item|Amount|Label)\b",
                line,
                re.IGNORECASE,
            ):
                pending_label = (pending_label + " " + line).strip()
            else:
                pending_label = ""
        else:
            low = line.lower()
            if re.match(r"^tax\s+offsets\b", low):
                in_tax_offsets = True
                continue
            if "amit cost base" in low or re.match(r"^part\s+e\b", low):
                in_tax_offsets = False
                part_b_rows.append(["Non-assessable Amounts", "", "", ""])
                if not amount_re.search(line):
                    continue
            if in_tax_offsets:
                continue
            if any(low.startswith(p) for p in skip_prefixes):
                continue

            amounts = amount_re.findall(line)
            if amounts:
                label = amount_re.split(line, maxsplit=1)[0].strip()
                label = re.sub(r"\s*\((?:[A-Z]\+)*[A-Z]\)\s*$", "", label)
                if "net cash" in label.lower() or "cost base" in label.lower():
                    part_b_rows.append(["Non-assessable Amounts", "", "", ""])
                part_b_rows.append([label, _norm_amt(amounts[-1]), "", ""])
            elif "non-assessable" in low:
                part_b_rows.append(["Non-assessable Amounts", "", "", ""])

    return part_a_rows, part_b_rows


def _parse_standard_amit(lines, amount_re):
    """Parse Automic, Magellan, and One Registry Services statements (Part B summary / Part C components)."""
    section = None
    part_a_rows = []
    part_b_rows = []
    dec_re = re.compile(r"\(?-?\$?[\d,]+\.\d{2}\)?")

    for line in lines:
        if any(
            line.startswith(s)
            for s in (
                "This guide provides general information",
                "End of Document",
                "IMPORTANT:",
                "Please retain",
            )
        ):
            break

        if re.match(r"^Part\s+B\b", line, re.IGNORECASE):
            section = "SUMMARY"
            continue
        if re.match(r"^Part\s+C\b", line, re.IGNORECASE) or re.search(
            r"Components?\s+of\s+(?:attribution|distribution)", line, re.IGNORECASE
        ):
            section = "COMPONENTS"
            continue

        if section == "SUMMARY":
            m = re.match(r"^(.*?)\s+(\(?-?\$?[\d,]+\.\d{2}\)?)\s+(\d{2}[A-Z])$", line)
            if m:
                part_a_rows.append([m.group(1).strip(), m.group(3), _norm_amt(m.group(2))])
        elif section == "COMPONENTS":
            cleaned = re.sub(r"\s+(?:\d{2}[A-Z](?:[/,]\s*\d{2}[A-Z])*|-)\s*$", "", line)
            amounts = dec_re.findall(cleaned)
            if amounts:
                label = dec_re.split(cleaned, maxsplit=1)[0].strip()
                label = re.sub(r"\s*\([A-Z]\)\s*$", "", label)
                if label.lower().startswith("less "):
                    label = "Less " + label[5:]
                if "net cash" in label.lower() or "cost base" in label.lower():
                    part_b_rows.append(["Non-assessable Amounts", "", "", ""])
                part_b_rows.append([label, _norm_amt(amounts[-1]), "", ""])
            elif "non-assessable" in line.lower():
                part_b_rows.append(["Non-assessable Amounts", "", "", ""])

    return part_a_rows, part_b_rows


def text_to_rows(full_text):
    """Auto-detect provider layout from statement text and normalize to CSV rows."""
    provider = detect_provider(full_text)
    if provider == "unknown":
        raise ValueError(
            "Unsupported format: could not detect Computershare, Link/MUFG, Automic, Magellan, or One Registry."
        )

    lines = [line.strip() for line in full_text.splitlines() if line.strip()]
    amount_re = re.compile(r"\(?-?\$[\d,]+\.\d{2}\)?")

    ticker = extract_ticker(lines, provider)
    entity = extract_entity(lines)
    fy_date = extract_fy_date(lines)

    rows = [
        [ticker],
        [entity],
        [fy_date],
        ["Part A"],
        ["Item", "Label", "Amount"],
    ]

    if provider == "computershare":
        part_a_rows, part_b_rows = _parse_computershare(lines, amount_re)
    elif provider == "link":
        part_a_rows, part_b_rows = _parse_link_mufg(lines, amount_re)
    else:
        part_a_rows, part_b_rows = _parse_standard_amit(lines, amount_re)

    rows.extend(part_a_rows)
    rows.append(["Part B"])
    rows.extend(part_b_rows)
    return rows


def pdf_to_rows(pdf_path):
    """Extract text from PDF and normalize to CSV rows."""
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return text_to_rows(full_text)


def part_a(acc_dict, ats_list, idx_b, key, balance, writer):
    """form transaction splits and balance - Part A"""
    for i, r in enumerate(ats_list[4]):
        if "amount" in r.lower():
            c = i
        if "label" in r.lower():
            label_c = i
    ncg = "0.00"
    for r in ats_list[5:idx_b]:
        if (
            len(r) > max(c, label_c)
            and r[c]
            and _norm_amt(r[c]) != "0.00"
            and re.compile(r"^\d{2}\D$").search(r[label_c]) is not None
        ):
            label = r[label_c]
            cfg = acc_dict.get(label)
            if cfg is None:
                print(f"Item label '{label}' does not occur in Tax Accounts, processing failed.")
                sys.exit(1)
            typ = cfg.get("Type") or ""
            amount = _apply_sign(r[c], typ)
            account = cfg.get("Account")
            if label == "18A":
                ncg = amount
            elif label == "18H":
                amount = "-" + _norm_amt(r[c])
                c2d = lambda x: str(x)[:-2] + "." + str(x)[-2:]
                amount = c2d((int(amount.replace(".", "")) - int(ncg.replace(".", ""))))
                account = "Income:Distribution:18H:GCTGrossUp"
            if label != "20M":
                row, balance = txn_split(key, account, amount, balance)
                _ = writer.writerow(row)
    return balance


def _norm_label(text):
    """Normalise dashes, hyphens, and whitespace for fuzzy matching."""
    text = re.sub(r"[–—]", "-", text.strip()).lower()
    text = text.replace("tax deferred", "tax-deferred").replace("tax free", "tax-free")
    text = text.replace("amit cost base net increase amount", "amit cost base net amount - shortfall")
    text = text.replace("amit cost base net decrease amount", "amit cost base net amount - excess")
    text = re.sub(r"\s*-\s*", "-", text)
    return re.sub(r"\s+", " ", text)


def dictionary_key_fuzzy_match(d, search):
    """Return matching keys, preferring exact or longest substring match."""
    norm_search = _norm_label(search)
    exact = [k for k in [*d] if _norm_label(k) == norm_search]
    if exact:
        return exact
    matches = [k for k in [*d] if _norm_label(k) in norm_search]
    if len(matches) > 1:
        matches.sort(key=lambda k: len(_norm_label(k)), reverse=True)
        return [matches[0]]
    return matches


def part_b(acc_dict, ats_list, idx_b, key, balance, writer):
    """form transaction splits and balance - Part B"""
    skip = True
    for r in ats_list[idx_b:]:
        if skip:
            if r and "Non-assessable Amounts".upper() in r[0].upper():
                skip = False
        else:
            for c in [1, 2, 3]:
                if (
                    len(r) > c
                    and r[c]
                    and _norm_amt(r[c]) != "0.00"
                    and re.compile(r"^\(?-?\$?[0-9,]*\.[0-9]{2}\)?$").search(r[c]) is not None
                ):
                    label_list = dictionary_key_fuzzy_match(acc_dict, r[0])
                    if not len(label_list):
                        print(
                            "Label: ",
                            r[0],
                            "does not occur in Tax Accounts, processing failed.",
                        )
                        sys.exit(1)
                    label = label_list[0]
                    cfg = acc_dict.get(label.upper())
                    if cfg is None:
                        print(
                            "Label: ",
                            r[0],
                            "does not occur in Tax Accounts, processing failed.",
                        )
                        sys.exit(1)
                    typ = cfg.get("Type") or ""
                    if typ.lower() == "skip":
                        break
                    amount = _apply_sign(r[c], typ)
                    account = cfg.get("Account")
                    row, balance = txn_split(key, account, amount, balance)
                    _ = writer.writerow(row)
    return balance


def close_txn(acc_dict, key, balance, writer):
    if balance != 0:
        if abs(balance) >= 3:
            print(
                f"WARNING: Rounding adjustment for {key[2]} ({key[0]}) is {-1 * balance / 100:.2f} "
                f"(>= $0.03), check for unmapped or skipped components.",
                file=sys.stderr,
            )
        account = acc_dict.get("Rounding".upper()).get("Account")
        amount = f"{-1 * balance / 100:.2f}"
        row, balance = txn_split(key, account, amount, balance)
        _ = writer.writerow(row)
    return balance


def main():
    try:
        args = get_args()
        app_dir = (
            os.path.dirname(os.path.abspath(sys.executable))
            if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__))
        )
        tax_acc_path = (
            "tax-acc.csv"
            if os.path.exists("tax-acc.csv")
            else os.path.join(app_dir, "tax-acc.csv")
        )
        try:
            acc_dict = csv_dictionary(tax_acc_path)
        except FileNotFoundError:
            sys.exit(
                f"Error: tax-acc.csv not found in the current directory or in '{app_dir}'."
            )

        ext = args.filename[-4:].lower()
        if ext == ".csv":
            cdf = args.filename
            csvs = cdf[:-4] + "_split.csv"
            with open(cdf, newline="") as ifile:
                ats_list = list(csv.reader(ifile))
        elif ext == ".txt":
            csvs = args.filename[:-4] + "_split.csv"
            with open(args.filename, "r", encoding="utf-8") as ifile:
                ats_list = text_to_rows(ifile.read())
        else:
            pdf = (
                args.filename
                if ext == ".pdf"
                else args.filename + ".pdf"
            )
            csvs = pdf[:-4] + "_split.csv"
            ats_list = pdf_to_rows(pdf)

        idx_b, _ = row_idx(ats_list, "Part B")[0]

        key = [
            re.sub(r"\s+", "", ats_list[1][0]),
            parser.parse(ats_list[2][0]).date().strftime("%d/%m/%Y"),
            ats_list[0][0],
        ]

        with open(csvs, "w", newline="") as ofile:
            writer = csv.writer(ofile, delimiter=",", quotechar='"')
            balance = 0
            balance = part_a(acc_dict, ats_list, idx_b, key, balance, writer)
            balance = part_b(acc_dict, ats_list, idx_b, key, balance, writer)
            balance = close_txn(acc_dict, key, balance, writer)
            if balance != 0:
                print(
                    f"WARNING: Non-zero net balance remaining for {key[2]} ({key[0]}): {balance / 100:.2f}",
                    file=sys.stderr,
                )
        print("done.")
    except IndexError:
        print("Unknown statement structure, processing failed.")


if __name__ == "__main__":
    main()
