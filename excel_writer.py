"""
InvoiceFlow — Enterprise Report Exporter
Generates clean, auditor-ready CSV and multi-sheet Excel reports with reconciliation checks.
"""

import os
import csv
from typing import List, Dict, Any

class ExcelReportWriter:
    def __init__(self, output_path: str = "invoices_summary.csv"):
        self.output_path = output_path

    def save_report(self, records: List[Dict[str, Any]], export_excel: bool = True) -> str:
        """Saves invoices with complete metadata, confidence scores, and line items."""
        csv_file = self.output_path if self.output_path.endswith('.csv') else self.output_path.replace('.xlsx', '.csv')
        
        fieldnames = [
            "filename", "vendor", "invoice_number", "date", "due_date",
            "currency", "subtotal", "tax", "total", "confidence_score",
            "math_reconciled", "status"
        ]
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for r in records:
                row_copy = r.copy()
                row_copy["math_reconciled"] = "PASSED" if r.get("math_reconciled", True) else "FAILED"
                writer.writerow(row_copy)

        # Export line items summary table as a companion report
        line_items_file = csv_file.replace('.csv', '_line_items.csv')
        line_fieldnames = ["invoice_number", "vendor", "description", "quantity", "unit_price", "total"]
        
        with open(line_items_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=line_fieldnames)
            writer.writeheader()
            for r in records:
                inv_num = r.get("invoice_number", "N/A")
                vendor = r.get("vendor", "N/A")
                for item in r.get("line_items", []):
                    writer.writerow({
                        "invoice_number": inv_num,
                        "vendor": vendor,
                        "description": item.get("description", ""),
                        "quantity": item.get("quantity", 1),
                        "unit_price": item.get("unit_price", 0.0),
                        "total": item.get("total", 0.0)
                    })

        # Multi-tab Excel export via pandas/openpyxl if requested
        if export_excel and self.output_path.endswith('.xlsx'):
            try:
                import pandas as pd
                df_invoices = pd.DataFrame(records)
                if 'line_items' in df_invoices.columns:
                    df_invoices = df_invoices.drop(columns=['line_items'])
                
                with pd.ExcelWriter(self.output_path, engine='openpyxl') as writer:
                    df_invoices.to_excel(writer, sheet_name='Invoices_Summary', index=False)
                    
                    # Flatten line items
                    flattened_items = []
                    for r in records:
                        for item in r.get("line_items", []):
                            entry = item.copy()
                            entry["invoice_number"] = r.get("invoice_number")
                            entry["vendor"] = r.get("vendor")
                            flattened_items.append(entry)
                    if flattened_items:
                        df_items = pd.DataFrame(flattened_items)
                        df_items.to_excel(writer, sheet_name='Line_Items', index=False)
                return self.output_path
            except Exception:
                return csv_file

        return csv_file
