"""
Comprehensive verification test script for monthly cash flow, expected inflow,
risk deductions, shortfall calculations, and expense recommendations.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.services.monthly_cashflow_service import MonthlyCashflowService
from app.schemas.prediction import PredictInvoiceRequest
from app.services.prediction_service import PredictionService

def test_monthly_cashflow():
    print("=================================================================")
    print("TEST SUITE: Monthly Cashflow, Expected Inflows & Shortfall Engine")
    print("=================================================================")

    svc = MonthlyCashflowService()
    # Clean test state
    svc._monthly_inflows.clear()
    svc._invoices.clear()

    # 1. Store expected inflow by month
    print("\n--- 1. Testing Monthly Expected Inflow Storage ---")
    inflow_nov = svc.set_expected_inflow("2026-11", 100000.0)
    assert inflow_nov == 100000.0
    assert svc.get_expected_inflow("2026-11") == 100000.0
    print("Stored November 2026 expected inflow: ₹1,00,000")

    # Update existing value without creating duplicate record
    svc.set_expected_inflow("2026-11", 100000.0)
    assert len(svc.get_all_monthly_inflows()) == 1
    print("Verified updating existing month updates in place without duplicates.")

    # Inflow for December
    svc.set_expected_inflow("2026-12", 150000.0)
    assert svc.get_expected_inflow("2026-12") == 150000.0
    print("Stored December 2026 expected inflow: ₹1,50,000")

    # 2. Risk-based shortfall calculation: Low risk invoice
    print("\n--- 2. Testing Low-Risk Invoice (Zero Deduction) ---")
    svc.record_invoice(
        invoice_id="INV-LOW-1",
        company_name="Prompt Payer Corp",
        invoice_amount=25000.0,
        due_date="2026-11-15",
        risk_level="Low Risk",
        risk_probability=0.15,
        predicted_delay_days=0,
    )
    summary_nov = svc.calculate_monthly_summary("2026-11")
    print(f"November Expected Inflow: ₹{summary_nov['manually_entered_expected_inflow']:,.0f}")
    print(f"November High-Risk Deductions: ₹{summary_nov['high_risk_deductions']:,.0f}")
    print(f"November Adjusted Inflow: ₹{summary_nov['adjusted_expected_inflow']:,.0f}")
    assert summary_nov["high_risk_deductions"] == 0.0, "Low risk invoice should have 0 deductions!"
    assert summary_nov["adjusted_expected_inflow"] == 100000.0, "Expected inflow should remain ₹1,00,000!"

    # 3. High-risk invoice due in November
    print("\n--- 3. Testing High-Risk Invoice Deduction ---")
    svc.record_invoice(
        invoice_id="INV-HIGH-1",
        company_name="Risky Debtor LLC",
        invoice_amount=20000.0,
        due_date="2026-11-20",
        risk_level="High Risk",
        risk_probability=0.82,
        predicted_delay_days=18,
    )
    summary_nov = svc.calculate_monthly_summary("2026-11")
    print(f"November High-Risk Deductions: ₹{summary_nov['high_risk_deductions']:,.0f}")
    print(f"November Adjusted Inflow: ₹{summary_nov['adjusted_expected_inflow']:,.0f}")
    assert summary_nov["high_risk_deductions"] == 20000.0, "High risk invoice should deduct ₹20,000!"
    assert summary_nov["adjusted_expected_inflow"] == 80000.0, "Adjusted inflow should be ₹80,000!"
    print("Confirmed: ₹1,00,000 expected - ₹20,000 high risk = ₹80,000 adjusted inflow.")

    # 4. Multiple high-risk invoices in the same month without double counting
    print("\n--- 4. Testing Multiple High-Risk Invoices in Same Month ---")
    svc.record_invoice(
        invoice_id="INV-HIGH-2",
        company_name="Another Late Debtor Inc",
        invoice_amount=15000.0,
        due_date="2026-11-25",
        risk_level="High Risk",
        risk_probability=0.75,
        predicted_delay_days=14,
    )
    summary_nov = svc.calculate_monthly_summary("2026-11")
    print(f"November High-Risk Deductions: ₹{summary_nov['high_risk_deductions']:,.0f}")
    print(f"November Adjusted Inflow: ₹{summary_nov['adjusted_expected_inflow']:,.0f}")
    assert summary_nov["high_risk_deductions"] == 35000.0, "Both high risk invoices should deduct: 20k + 15k = 35k!"
    assert summary_nov["adjusted_expected_inflow"] == 65000.0, "Adjusted inflow should be ₹65,000!"

    # Processing the same invoice again (idempotent / no duplicate deduction)
    svc.record_invoice(
        invoice_id="INV-HIGH-2",
        company_name="Another Late Debtor Inc",
        invoice_amount=15000.0,
        due_date="2026-11-25",
        risk_level="High Risk",
        risk_probability=0.75,
        predicted_delay_days=14,
    )
    summary_nov_re = svc.calculate_monthly_summary("2026-11")
    assert summary_nov_re["high_risk_deductions"] == 35000.0, "Re-processing invoice must not double count deduction!"
    print("Verified idempotent invoice recording prevents duplicate deductions.")

    # 5. Invoices with different due months affect ONLY their respective months
    print("\n--- 5. Testing Invoices with Different Due Months ---")
    svc.record_invoice(
        invoice_id="INV-DEC-1",
        company_name="December Debtor Co",
        invoice_amount=30000.0,
        due_date="2026-12-10",
        risk_level="High Risk",
        risk_probability=0.88,
        predicted_delay_days=20,
    )
    summary_dec = svc.calculate_monthly_summary("2026-12")
    summary_nov_after = svc.calculate_monthly_summary("2026-11")

    print(f"December Expected: ₹{summary_dec['manually_entered_expected_inflow']:,.0f}, Deductions: ₹{summary_dec['high_risk_deductions']:,.0f}, Adjusted: ₹{summary_dec['adjusted_expected_inflow']:,.0f}")
    print(f"November Deductions after Dec invoice added: ₹{summary_nov_after['high_risk_deductions']:,.0f}")
    assert summary_dec["high_risk_deductions"] == 30000.0
    assert summary_dec["adjusted_expected_inflow"] == 120000.0
    assert summary_nov_after["high_risk_deductions"] == 35000.0, "December invoice must not affect November!"
    print("Confirmed: Invoices affect only the month corresponding to their due dates.")

    # 6. Recalculation on invoice deletion
    print("\n--- 6. Testing Deletion & Deduction Recalculation ---")
    deleted = svc.delete_invoice("INV-HIGH-2")
    assert deleted is True
    summary_nov_del = svc.calculate_monthly_summary("2026-11")
    print(f"November Deductions after deleting INV-HIGH-2: ₹{summary_nov_del['high_risk_deductions']:,.0f}")
    assert summary_nov_del["high_risk_deductions"] == 20000.0, "Deductions should drop back to ₹20,000!"
    assert summary_nov_del["adjusted_expected_inflow"] == 80000.0, "Adjusted inflow should restore to ₹80,000!"
    print("Confirmed: Recalculates deductions dynamically upon invoice deletion.")

    # 7. Expense recommendations & Shortfall calculation
    print("\n--- 7. Testing Expense Recommendations & Shortfall Logic ---")
    print(f"Status: {summary_nov_del['status']}")
    print(f"Potential Shortfall: ₹{summary_nov_del['potential_shortfall']:,.0f}")
    print(f"Essential Expenses: ₹{summary_nov_del['essential_expenses_total']:,.0f}")
    print(f"Deferrable Expenses: ₹{summary_nov_del['deferrable_expenses_total']:,.0f}")
    print("Recommendations:")
    for r in summary_nov_del["recommendations"]:
        print(f"  • {r}")

    # Check essential expenses prioritized
    assert summary_nov_del["essential_expenses_total"] == 80000.0
    assert summary_nov_del["potential_shortfall"] == 35000.0  # 115k planned - 80k adjusted = 35k shortfall
    assert any("PRIORITISE UNAVOIDABLE EXPENSES" in r for r in summary_nov_del["recommendations"])
    assert any("RECOMMEND POSTPONING" in r for r in summary_nov_del["recommendations"])

    # 8. Testing End-to-End PredictionService with Random Forest & SHAP
    print("\n--- 8. Testing End-to-End PredictionService with Random Forest + SHAP ---")
    pred_svc = PredictionService(user_id="default")
    req = PredictInvoiceRequest(
        company_name="1604-LIFKX",
        invoice_amount=20000.0,
        order_date="2026-11-01",
        due_date="2026-11-28",
        expected_inflow=100000.0,
        invoice_id="INV-PRED-NOV-TEST",
    )
    resp = pred_svc.predict_invoice(req)
    print(f"Prediction: {resp.prediction}")
    print(f"Risk Level: {resp.risk_level} ({resp.risk_probability * 100:.1f}%)")
    print(f"SHAP Values count: {len(resp.shap_values)}")
    print(f"Due Month: {resp.due_month} ({resp.month_label})")
    print(f"Monthly Expected Inflow: ₹{resp.monthly_expected_inflow:,.0f}")
    print(f"High-Risk Deductions: ₹{resp.high_risk_deductions:,.0f}")
    print(f"Adjusted Inflow: ₹{resp.adjusted_inflow:,.0f}")
    print(f"Potential Shortfall: ₹{resp.potential_shortfall:,.0f}")

    assert resp.due_month == "2026-11"
    assert resp.monthly_expected_inflow == 100000.0
    assert resp.shap_values is not None and len(resp.shap_values) > 0, "SHAP values must be preserved!"
    print("Random Forest and SHAP explanation verified successfully!")

    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_monthly_cashflow()
