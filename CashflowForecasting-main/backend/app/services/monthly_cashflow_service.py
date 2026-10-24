"""
Monthly Cash Flow & Risk-Based Shortfall Service.

Implements monthly expected inflow storage, risk-based deductions for invoices,
shortfall calculation, and expense prioritization recommendations.

Key Invariants:
1. Expected inflow is a manually entered monthly financial figure; it is NEVER
   calculated by summing invoice amounts.
2. Invoices only affect the month and year of their due date.
3. Low-risk invoices cause ZERO deductions.
4. High-risk invoices deduct their invoice amount from the expected inflow of their due month.
5. Invoices are tracked by unique ID to prevent duplicate deductions.
6. Deductions are dynamically recalculated when invoices are added, updated, or removed.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

STORE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "monthly_cashflow_store.json")

# Standard monthly expense commitments (defaults, customizable)
DEFAULT_ESSENTIAL_EXPENSES = [
    {"name": "Staff Salaries", "category": "essential", "amount": 45000.0, "description": "Core payroll commitments (unavoidable)"},
    {"name": "Office & Facility Rent", "category": "essential", "amount": 25000.0, "description": "Physical lease obligations (unavoidable)"},
    {"name": "Electricity & Utility Bills", "category": "essential", "amount": 10000.0, "description": "Power, water, and connectivity bills (unavoidable)"},
]

DEFAULT_DEFERRABLE_EXPENSES = [
    {"name": "Eligible Investments & Capex", "category": "deferrable", "amount": 15000.0, "description": "Long-term expansion and hardware upgrades (deferrable)"},
    {"name": "Raw Material Advance Orders", "category": "deferrable", "amount": 12000.0, "description": "Buffer inventory and non-critical materials (deferrable)"},
    {"name": "Optional Discretionary Purchases", "category": "deferrable", "amount": 8000.0, "description": "Software upgrades and office refurbishments (deferrable)"},
]


def extract_year_month(date_str: str) -> str:
    """Extract YYYY-MM from a date string (YYYY-MM-DD or similar)."""
    if not date_str:
        return datetime.now().strftime("%Y-%m")
    clean = str(date_str).strip()
    match = re.match(r"^(\d{4})[-/.](\d{1,2})", clean)
    if match:
        year, month = match.groups()
        return f"{int(year):04d}-{int(month):02d}"
    try:
        dt = datetime.strptime(clean[:10], "%Y-%m-%d")
        return dt.strftime("%Y-%m")
    except Exception:
        return datetime.now().strftime("%Y-%m")


def format_month_label(year_month: str) -> str:
    """Format YYYY-MM into 'Month Year' e.g. 'November 2026'."""
    try:
        dt = datetime.strptime(year_month, "%Y-%m")
        return dt.strftime("%B %Y")
    except Exception:
        return year_month


class MonthlyCashflowService:
    """
    Manages monthly expected inflows, risk deductions, shortfall calculations,
    and expense recommendations.
    """

    _instance: Optional["MonthlyCashflowService"] = None

    def __new__(cls) -> "MonthlyCashflowService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._store_path = STORE_FILE
        self._monthly_inflows: Dict[str, float] = {}  # { "2026-11": 100000.0 }
        self._invoices: Dict[str, Dict[str, Any]] = {}  # { invoice_id: { ... } }
        self._custom_expenses: Dict[str, List[Dict[str, Any]]] = {}  # { "2026-11": [ ... ] }
        self._load_store()
        self._initialized = True

    # ------------------------------------------------------------------ #
    # Persistence helpers                                                #
    # ------------------------------------------------------------------ #

    def _load_store(self) -> None:
        """Load state from persistent JSON file if present."""
        if os.path.isfile(self._store_path):
            try:
                with open(self._store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._monthly_inflows = data.get("monthly_inflows", {})
                    self._invoices = data.get("invoices", {})
                    self._custom_expenses = data.get("custom_expenses", {})
            except Exception:
                pass

    def _save_store(self) -> None:
        """Write current state to persistent JSON file."""
        try:
            data = {
                "monthly_inflows": self._monthly_inflows,
                "invoices": self._invoices,
                "custom_expenses": self._custom_expenses,
            }
            with open(self._store_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Expected Inflow Management                                         #
    # ------------------------------------------------------------------ #

    def set_expected_inflow(self, year_month: str, amount: float) -> float:
        """
        Store or update manually entered expected inflow for a month.
        Does NOT sum invoice amounts.
        If an expected inflow for that month exists, updates it.
        """
        clean_ym = extract_year_month(year_month)
        val = max(0.0, float(amount))
        self._monthly_inflows[clean_ym] = val
        self._save_store()
        return val

    def get_expected_inflow(self, year_month: str) -> Optional[float]:
        """Get manually entered expected inflow for a month, or None if unset."""
        clean_ym = extract_year_month(year_month)
        return self._monthly_inflows.get(clean_ym)

    def get_all_monthly_inflows(self) -> Dict[str, float]:
        """Return all stored monthly expected inflows."""
        return dict(self._monthly_inflows)

    # ------------------------------------------------------------------ #
    # Invoice Tracking & Deductions                                      #
    # ------------------------------------------------------------------ #

    def record_invoice(
        self,
        invoice_id: str,
        company_name: str,
        invoice_amount: float,
        due_date: str,
        risk_level: str,
        risk_probability: float,
        predicted_delay_days: int = 0,
        order_date: Optional[str] = None,
        shap_explanation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Records an invoice prediction.
        Prevents duplicate deductions by storing by unique invoice_id.
        Deductions are applied strictly based on the invoice's due-date month.
        """
        due_month = extract_year_month(due_date)
        is_high_risk = str(risk_level).strip().lower() == "high risk"

        record = {
            "invoice_id": invoice_id,
            "company_name": company_name,
            "invoice_amount": float(invoice_amount),
            "order_date": order_date or due_date,
            "due_date": due_date,
            "due_month": due_month,
            "risk_level": risk_level,
            "risk_probability": float(risk_probability),
            "predicted_delay_days": int(predicted_delay_days),
            "is_high_risk": is_high_risk,
            "deducted_amount": float(invoice_amount) if is_high_risk else 0.0,
            "shap_explanation": shap_explanation or {},
            "updated_at": datetime.now().isoformat(),
        }

        self._invoices[invoice_id] = record
        self._save_store()
        return record

    def delete_invoice(self, invoice_id: str) -> bool:
        """
        Removes an invoice and recalculates monthly deductions.
        """
        if invoice_id in self._invoices:
            del self._invoices[invoice_id]
            self._save_store()
            return True
        return False

    def get_invoices_for_month(self, year_month: str) -> List[Dict[str, Any]]:
        """Return all invoices due in the specified month."""
        clean_ym = extract_year_month(year_month)
        return [inv for inv in self._invoices.values() if inv.get("due_month") == clean_ym]

    # ------------------------------------------------------------------ #
    # Shortfall & Recommendation Engine                                  #
    # ------------------------------------------------------------------ #

    def calculate_monthly_summary(self, year_month: str) -> Dict[str, Any]:
        """
        Calculates monthly cash flow, high-risk deductions, adjusted inflow,
        shortfall, and expense recommendations for a selected month and year.
        """
        clean_ym = extract_year_month(year_month)
        month_label = format_month_label(clean_ym)

        # 1. Manually entered expected inflow (default to 0.0 if not yet entered)
        expected_inflow = self._monthly_inflows.get(clean_ym, 0.0)

        # 2. Get all invoices due strictly in this month
        month_invoices = self.get_invoices_for_month(clean_ym)

        # 3. High-risk deductions: Sum amounts of high-risk invoices due in this month
        high_risk_invoices = [inv for inv in month_invoices if inv.get("is_high_risk")]
        low_risk_invoices = [inv for inv in month_invoices if not inv.get("is_high_risk")]

        high_risk_deductions = sum(inv.get("invoice_amount", 0.0) for inv in high_risk_invoices)

        # 4. Adjusted expected inflow = original expected inflow - high risk deductions
        adjusted_inflow = max(0.0, expected_inflow - high_risk_deductions)

        # 5. Commitments & Expenses
        essential_expenses = list(DEFAULT_ESSENTIAL_EXPENSES)
        deferrable_expenses = list(DEFAULT_DEFERRABLE_EXPENSES)

        total_essential = sum(e["amount"] for e in essential_expenses)
        total_deferrable = sum(e["amount"] for e in deferrable_expenses)
        total_planned_expenses = total_essential + total_deferrable

        # 6. Potential shortfall calculation
        # If adjusted inflow is less than total planned expenses, a shortfall exists
        shortfall = max(0.0, total_planned_expenses - adjusted_inflow)
        surplus = max(0.0, adjusted_inflow - total_planned_expenses)

        # Critical shortfall on essential expenses if adjusted inflow < essential commitments
        essential_shortfall = max(0.0, total_essential - adjusted_inflow)

        # 7. Expense recommendations
        recommendations = []
        status_code = "NO_SHORTFALL"

        if shortfall > 0:
            status_code = "SHORTFALL_DETECTED"
            recommendations.append(
                f"Potential liquidity shortfall of ₹{shortfall:,.0f} detected for {month_label} due to high-risk invoice delays."
            )
            recommendations.append(
                "PRIORITISE UNAVOIDABLE EXPENSES: Guarantee on-time disbursement for staff salaries, office rent, and utility bills."
            )
            recommendations.append(
                "RECOMMEND POSTPONING: Defer non-critical raw material orders, capital investments, and discretionary purchases to protect cash reserves."
            )
            recommendations.append(
                "SAFETY RULE: Do not postpone essential expenses (rent, electricity, salaries) as the default solution."
            )
        else:
            status_code = "SUFFICIENT_LIQUIDITY"
            recommendations.append(
                f"Healthy financial position for {month_label}. Adjusted inflow of ₹{adjusted_inflow:,.0f} covers all commitments with an available buffer of ₹{surplus:,.0f}."
            )
            recommendations.append(
                "Planned raw material purchases, capital investments, and optional equipment orders can proceed without disruption."
            )

        return {
            "year_month": clean_ym,
            "month_label": month_label,
            "manually_entered_expected_inflow": expected_inflow,
            "high_risk_deductions": high_risk_deductions,
            "adjusted_expected_inflow": adjusted_inflow,
            "potential_shortfall": shortfall,
            "available_surplus": surplus,
            "status": status_code,
            "total_planned_expenses": total_planned_expenses,
            "essential_expenses_total": total_essential,
            "deferrable_expenses_total": total_deferrable,
            "essential_expenses": essential_expenses,
            "deferrable_expenses": deferrable_expenses,
            "recommendations": recommendations,
            "invoices_count": len(month_invoices),
            "high_risk_invoices_count": len(high_risk_invoices),
            "low_risk_invoices_count": len(low_risk_invoices),
            "invoices": month_invoices,
        }


# Global singleton instance
monthly_cashflow_service = MonthlyCashflowService()
