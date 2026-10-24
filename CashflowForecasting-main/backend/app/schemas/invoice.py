"""
Pydantic schemas for invoice request and response bodies.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class InvoiceMeta(BaseModel):
    """Metadata model for an individual invoice record."""
    id: str
    dataset_id: str
    user_id: str
    invoice_number: Optional[str] = None
    customer_id: Optional[str] = None
    country_code: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    settled_date: Optional[str] = None
    invoice_amount: Optional[float] = None
    disputed: Optional[bool] = None
    paperless_bill: Optional[bool] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class InvoiceListResponse(BaseModel):
    """Paginated list response for invoices."""
    invoices: List[InvoiceMeta]
    total: int
    page: int
    limit: int
    pages: int
