#!/usr/bin/env python3
# coding: utf-8

"""
Try to guess if commerce documents are present and signed
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import os
import csv
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

csv_writter = csv.writer(open("check_signed_pdf_result.csv", "w"), dialect="excel")
csv_writter.writerow(["lead", "pdf files", "Office pdf files", "pdf types", "diag"])

for dirpath, dirnames, filenames in os.walk("."):
    if not dirpath.endswith("/commerce"):
        continue
    lead = dirpath.split("/")[-2]
    print(f"======= {lead} =======")
    pdf = []
    for filename in filenames:
        if not filename.endswith(".pdf"):
            continue
        try:
            reader = PdfReader(os.path.join(dirpath, filename))
            pdf.append(reader.metadata.creator or "unknown")
        except PdfReadError:
            pdf.append("unreadable pdf")
        except AttributeError:
            pdf.append("unreadable file")
    pdf_count = len(pdf)
    microsoft_pdf_count = len([i for i in pdf if "Microsoft" in i])
    if pdf_count < 2:
        msg = f"{lead} has only {pdf_count} PDF files in commerce dir"
    elif pdf_count > 1 and microsoft_pdf_count == pdf_count:
        msg = f"{lead} only have Ms Office PDF in commerce dir. Signed PDF may be missing"
    else:
        msg = "Looks good"
    print(pdf)
    print(msg)
    csv_writter.writerow([lead, pdf_count, microsoft_pdf_count, "|".join(pdf), msg])