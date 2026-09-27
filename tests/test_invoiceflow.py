"""
Unit & Integration Tests for InvoiceFlow-automation
Validates extraction accuracy, line item parsing, math checks, and SQLite persistence.
"""

import os
import pytest
from extractor import InvoiceExtractor
from database import init_db, save_invoice, check_duplicate, get_all_invoices, update_status, get_summary_stats
from excel_writer import ExcelReportWriter

TEST_DB = "test_invoiceflow.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

SAMPLE_INVOICE_TEXT = """
Acme Cloud Services Inc.
Invoice Number: INV-99214
Invoice Date: 2025-03-15
Due Date: 2025-04-15
Tax ID: GSTIN-882914
Bill To: Enterprise Dynamics LLC

Items:
Server Hosting Pro  2  $150.00  $300.00
Cloud Storage 10TB  1  $200.00  $200.00

Subtotal: $500.00
Tax: $50.00
Grand Total: $550.00
"""

def test_invoice_extraction():
    extractor = InvoiceExtractor()
    result = extractor.extract_from_text(SAMPLE_INVOICE_TEXT, "sample_acme.txt")
    
    assert result["vendor"] == "Acme Cloud Services Inc."
    assert result["invoice_number"] == "INV-99214"
    assert result["date"] == "2025-03-15"
    assert result["subtotal"] == 500.00
    assert result["tax"] == 50.00
    assert result["total"] == 550.00
    assert result["math_reconciled"] is True
    assert len(result["line_items"]) == 2
    assert result["confidence_score"] >= 85

def test_arithmetic_discrepancy_detection():
    broken_text = """
    Bad Math Corp
    Invoice No: INV-BAD-1
    Date: 2025-01-01
    Subtotal: $400.00
    Tax: $20.00
    Grand Total: $999.00
    """
    extractor = InvoiceExtractor()
    result = extractor.extract_from_text(broken_text, "bad_math.txt")
    
    assert result["math_reconciled"] is False
    assert result["status"] == "REVIEW_REQUIRED"

def test_sqlite_persistence_and_duplicate_check():
    extractor = InvoiceExtractor()
    result = extractor.extract_from_text(SAMPLE_INVOICE_TEXT, "sample_acme.txt")
    
    # Check no duplicate before save
    dup_before = check_duplicate(result["invoice_number"], result["file_hash"], db_path=TEST_DB)
    assert dup_before is None
    
    # Save invoice
    inv_id = save_invoice(result, db_path=TEST_DB)
    assert inv_id > 0
    
    # Duplicate should now trigger
    dup_after = check_duplicate(result["invoice_number"], result["file_hash"], db_path=TEST_DB)
    assert dup_after is not None
    assert dup_after["invoice_number"] == "INV-99214"
    
    # Update status
    update_status(inv_id, "APPROVED", "Verified by Senior Auditor", db_path=TEST_DB)
    invoices = get_all_invoices(db_path=TEST_DB)
    assert len(invoices) == 1
    assert invoices[0]["status"] == "APPROVED"
    
    # Summary stats
    stats = get_summary_stats(db_path=TEST_DB)
    assert stats["total_invoices"] == 1
    assert stats["total_value"] == 550.00
    assert stats["approved_count"] == 1

def test_excel_and_csv_export(tmp_path):
    out_csv = os.path.join(tmp_path, "export.csv")
    writer = ExcelReportWriter(output_path=out_csv)
    
    records = [{
        "filename": "inv_1.txt",
        "vendor": "Acme",
        "invoice_number": "INV-100",
        "date": "2025-01-01",
        "due_date": "2025-01-31",
        "currency": "USD",
        "subtotal": 100.0,
        "tax": 10.0,
        "total": 110.0,
        "confidence_score": 95.0,
        "math_reconciled": True,
        "status": "APPROVED",
        "line_items": [{"description": "Item A", "quantity": 1, "unit_price": 100.0, "total": 100.0}]
    }]
    
    generated = writer.save_report(records, export_excel=False)
    assert os.path.exists(generated)
    assert os.path.exists(generated.replace('.csv', '_line_items.csv'))
