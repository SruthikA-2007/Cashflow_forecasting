"""
Reusable column mapping utility.
Maps dataset column names to standard application invoice fields.
"""

import re
from typing import List, Dict, Optional

# Target application fields for invoices
TARGET_FIELDS = [
    "invoice_number",
    "customer_id",
    "country_code",
    "invoice_date",
    "due_date",
    "settled_date",
    "invoice_amount",
    "disputed",
    "paperless_bill",
]

# Alias dictionary for variation matching
FIELD_ALIASES: Dict[str, List[str]] = {
    "invoice_number": [
        "invoice_number", "invoicenumber", "invoice_num", "invoicenum",
        "invoice_id", "invoiceid", "inv_num", "inv_no", "invoiceno", "invoice_no", "inv_id"
    ],
    "customer_id": [
        "customer_id", "customerid", "cust_id", "custid",
        "client_id", "clientid", "customer_num", "customernum", "customer_no"
    ],
    "country_code": [
        "country_code", "countrycode", "country", "country_id", "countryid", "nation", "location"
    ],
    "invoice_date": [
        "invoice_date", "invoicedate", "inv_date", "date_invoiced", "dateinvoiced",
        "invoice_dt", "date", "created_date"
    ],
    "due_date": [
        "due_date", "duedate", "payment_due_date", "paymentduedate", "due_dt", "due"
    ],
    "settled_date": [
        "settled_date", "settleddate", "settlement_date", "settlementdate",
        "paid_date", "paiddate", "settled_dt", "payment_date", "pay_date"
    ],
    "invoice_amount": [
        "invoice_amount", "invoiceamount", "amount", "total_amount", "totalamount",
        "inv_amount", "invamount", "price", "val", "value", "balance"
    ],
    "disputed": [
        "disputed", "is_disputed", "isdisputed", "dispute", "dispute_status", "disputed_flag"
    ],
    "paperless_bill": [
        "paperless_bill", "paperlessbill", "paperless_billing", "paperlessbilling",
        "is_paperless", "ispaperless", "paperless", "paperless_flag"
    ],
}


def _normalize(name: str) -> str:
    """Removes underscores, spaces, hyphens, and non-alphanumeric characters in lowercase."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def detect_column_mapping(columns: List[str]) -> Dict[str, Optional[str]]:
    """
    Detects and maps uploaded dataset column names to target application fields.

    Parameters
    ----------
    columns : List[str]
        List of column names from the uploaded dataset.

    Returns
    -------
    Dict[str, Optional[str]]
        Mapping of target application field -> matched dataset column name (or None).
    """
    mapping: Dict[str, Optional[str]] = {field: None for field in TARGET_FIELDS}
    normalized_dataset_cols = {_normalize(col): col for col in columns}

    for field, aliases in FIELD_ALIASES.items():
        matched_col = None
        for alias in aliases:
            norm_alias = _normalize(alias)
            if norm_alias in normalized_dataset_cols:
                matched_col = normalized_dataset_cols[norm_alias]
                break

        if not matched_col:
            field_norm = _normalize(field)
            for norm_col, orig_col in normalized_dataset_cols.items():
                if field_norm in norm_col or norm_col in field_norm:
                    matched_col = orig_col
                    break

        mapping[field] = matched_col

    return mapping
