"""
Invoice routes module.
Provides protected endpoints for querying individual invoices.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import get_current_user
from app.schemas.invoice import InvoiceMeta
from app.services.invoice_service import InvoiceService

router = APIRouter()


# ------------------------------------------------------------------
# GET /invoices/{invoice_id}
# ------------------------------------------------------------------
@router.get(
    "/{invoice_id}",
    response_model=InvoiceMeta,
    summary="Get single invoice by ID",
)
async def get_invoice(
    invoice_id: str,
    user=Depends(get_current_user),
):
    """
    Returns an individual invoice by ID.
    Verifies that the invoice belongs strictly to the authenticated user.
    Returns HTTP 404 if the invoice does not exist or access is denied.
    """
    user_id = str(getattr(user, "id", ""))
    svc = InvoiceService(user_id=user_id)
    invoice = svc.get_by_id(invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found or access denied.",
        )
    return invoice
