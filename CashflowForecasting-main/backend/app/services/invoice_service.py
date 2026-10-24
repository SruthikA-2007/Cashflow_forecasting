"""
Invoice service module.
Encapsulates database operations for fetching and paginating invoice records.
All operations strictly filter by the authenticated user's ID to prevent unauthorized access.
"""

from typing import Optional
from fastapi import HTTPException, status
from app.schemas.invoice import InvoiceMeta, InvoiceListResponse
from app.services.dataset_service import DatasetService
from app.supabase_client import supabase_admin

INVOICES_TABLE = "invoices"


class InvoiceService:
    """
    Service layer for invoice operations strictly scoped to the authenticated user.
    """

    def __init__(self, user_id: str) -> None:
        self._user_id = str(user_id)
        self._sb = supabase_admin

    def get_by_dataset(
        self, dataset_id: str, page: int = 1, limit: int = 50
    ) -> InvoiceListResponse:
        """
        Fetch paginated invoices for a specific dataset belonging strictly to the authenticated user.
        Raises HTTP 404 if dataset does not exist or does not belong to user.
        """
        dataset_svc = DatasetService(self._user_id)
        dataset = dataset_svc.get_by_id(dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or access denied.",
            )

        offset = (page - 1) * limit

        try:
            # Query count
            count_res = (
                self._sb.table(INVOICES_TABLE)
                .select("id", count="exact")
                .eq("dataset_id", str(dataset_id))
                .eq("user_id", self._user_id)
                .execute()
            )
            total = count_res.count if count_res and count_res.count is not None else 0

            # Query paginated rows
            response = (
                self._sb.table(INVOICES_TABLE)
                .select("*")
                .eq("dataset_id", str(dataset_id))
                .eq("user_id", self._user_id)
                .order("created_at", desc=False)
                .range(offset, offset + limit - 1)
                .execute()
            )
            data = response.data if response and response.data else []
            invoices = [InvoiceMeta(**dict(r)) for r in data]
            pages = (total + limit - 1) // limit if limit > 0 else 1

            return InvoiceListResponse(
                invoices=invoices,
                total=total,
                page=page,
                limit=limit,
                pages=max(pages, 1),
            )
        except Exception as e:
            # Fallback for empty or connection-restricted queries
            return InvoiceListResponse(
                invoices=[],
                total=0,
                page=page,
                limit=limit,
                pages=1,
            )

    def get_by_id(self, invoice_id: str) -> Optional[InvoiceMeta]:
        """
        Fetch a single invoice by ID, verifying user ownership.
        Returns None if invoice is missing or belongs to another user.
        """
        try:
            response = (
                self._sb.table(INVOICES_TABLE)
                .select("*")
                .eq("id", str(invoice_id))
                .eq("user_id", self._user_id)
                .execute()
            )
            if response and response.data and len(response.data) > 0:
                return InvoiceMeta(**dict(response.data[0]))
            return None
        except Exception:
            return None
