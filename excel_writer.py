"""
InvoiceFlow — Excel Report Writer & Deduplication Engine
"""

import os
import csv
from typing import List, Dict, Any

class ExcelReportWriter:
    def __init__(self, output_path: str = "invoices_summary.csv"):
        self.output_path = output_path
        self.seen_invoices = set()

    def deduplicate(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Flags or removes duplicate invoice numbers."""
        unique_records = []
        for rec in records:
            inv_id = rec.get("invoice_number")
            if inv_id in self.seen_invoices:
                rec["status"] = "DUPLICATE FLAGGED"
            else:
                self.seen_invoices.add(inv_id)
                rec["status"] = "VERIFIED"
            unique_records.append(rec)
        return unique_records

    def save_report(self, records: List[Dict[str, Any]], export_excel: bool = True) -> str:
        """Saves processed records to CSV/Excel report."""
        cleaned_records = self.deduplicate(records)
        
        # Write CSV report (accessible universally)
        csv_file = self.output_path if self.output_path.endswith('.csv') else self.output_path.replace('.xlsx', '.csv')
        fieldnames = ["filename", "vendor", "invoice_number", "date", "amount", "tax_id", "status"]
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(cleaned_records)

        # Attempt OpenPyXL export if available
        if export_excel and self.output_path.endswith('.xlsx'):
            try:
                import pandas as pd
                df = pd.DataFrame(cleaned_records)
                df.to_excel(self.output_path, index=False)
                return self.output_path
            except ImportError:
                return csv_file

        return csv_file
