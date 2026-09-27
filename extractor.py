"""
InvoiceFlow — Enterprise PDF & Invoice Field Extractor
Production-grade extraction with confidence scoring, line-item parsing,
mathematical reconciliation, and pure-Python PDF support.
"""

import os
import re
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime

class InvoiceExtractor:
    def __init__(self):
        # Optimized regex patterns for financial documents
        self.date_pattern = re.compile(
            r'\b(?:\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4})\b',
            re.IGNORECASE
        )
        self.due_date_pattern = re.compile(
            r'(?:Due Date|Payment Due|Pay By)[:\s]*([A-Za-z0-9\s,/-]+?)(?=\n|$|\s{2,})',
            re.IGNORECASE
        )
        self.invoice_num_pattern = re.compile(
            r'(?:Invoice\s*(?:No|Number|#)|INV[:#\s]*)[\s:]*([A-Z0-9-_]{3,20})',
            re.IGNORECASE
        )
        self.tax_id_pattern = re.compile(
            r'(?:Tax ID|GSTIN|VAT|EIN|Tax Registration)[:\s]*([A-Z0-9-]{8,20})',
            re.IGNORECASE
        )
        self.total_pattern = re.compile(
            r'\b(?:Grand Total|Total Amount|Amount Due|Balance Due|Net Payable|Total)\b[:\s]*([$€£₹]?\s*[\d,]+\.\d{2})',
            re.IGNORECASE
        )
        self.subtotal_pattern = re.compile(
            r'\b(?:Subtotal|Sub-Total|Net Amount|Total Before Tax)\b[:\s]*([$€£₹]?\s*[\d,]+\.\d{2})',
            re.IGNORECASE
        )
        self.tax_pattern = re.compile(
            r'\b(?:Tax|GST|VAT|Sales Tax|Estimated Tax)\b[:\s]*([$€£₹]?\s*[\d,]+\.\d{2})',
            re.IGNORECASE
        )
        self.currency_pattern = re.compile(r'([$€£₹]|USD|EUR|GBP|INR)')

    def _clean_amount(self, raw_str: Optional[str]) -> float:
        if not raw_str:
            return 0.0
        cleaned = re.sub(r'[^\d.]', '', raw_str)
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def _detect_currency(self, text: str) -> str:
        curr_match = self.currency_pattern.search(text)
        if curr_match:
            symbol = curr_match.group(1).upper()
            mapping = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}
            return mapping.get(symbol, symbol)
        return "USD"

    def extract_line_items(self, text: str) -> List[Dict[str, Any]]:
        """Parses structured line items with quantity, unit price, and total."""
        items = []
        lines = text.split('\n')
        
        # Pattern: Description ... Qty ... Price ... Total
        # e.g. "Cloud EC2 Instance  2  $150.00  $300.00" or "- Widget A x 3: $45.00"
        line_item_regex = re.compile(
            r'^(?:[-*•]\s*)?(.+?)\s+(\d+)\s+[$€£₹]?\s*([\d,]+\.\d{2})\s+[$€£₹]?\s*([\d,]+\.\d{2})$',
            re.IGNORECASE
        )
        
        fallback_item_regex = re.compile(
            r'^(?:[-*•]\s*)?(.+?)(?:\s+x\s*(\d+))?[:\s]+[$€£₹]?\s*([\d,]+\.\d{2})$',
            re.IGNORECASE
        )

        for line in lines:
            line_str = line.strip()
            if not line_str or any(kw in line_str.lower() for kw in ['subtotal', 'total', 'tax', 'balance due', 'invoice']):
                continue
            
            match = line_item_regex.match(line_str)
            if match:
                desc = match.group(1).strip()
                qty = int(match.group(2))
                unit_price = self._clean_amount(match.group(3))
                total = self._clean_amount(match.group(4))
                items.append({
                    "description": desc,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "total": total
                })
                continue
                
            fallback_match = fallback_item_regex.match(line_str)
            if fallback_match:
                desc = fallback_match.group(1).strip()
                qty = int(fallback_match.group(2)) if fallback_match.group(2) else 1
                total = self._clean_amount(fallback_match.group(3))
                unit_price = round(total / qty, 2) if qty > 0 else total
                items.append({
                    "description": desc,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "total": total
                })

        return items

    def extract_from_text(self, text: str, filename: str = "") -> Dict[str, Any]:
        """Performs robust multi-field extraction with confidence scoring and math reconciliation."""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # 1. Vendor Extraction Heuristic
        vendor = "Unknown Vendor"
        vendor_confidence = 0.5
        for line in lines[:5]:
            lower = line.lower()
            if not any(k in lower for k in ['invoice', 'bill to', 'date', 'tax', 'page', 'due', 'amount']):
                vendor = line
                vendor_confidence = 0.9 if len(line) > 3 else 0.6
                break

        # 2. Invoice Number
        inv_match = self.invoice_num_pattern.search(text)
        if inv_match:
            invoice_number = inv_match.group(1).strip()
            inv_confidence = 0.95
        else:
            invoice_number = f"INV-UNKNOWN"
            inv_confidence = 0.2

        # 3. Dates
        date_match = self.date_pattern.search(text)
        invoice_date = date_match.group(0).strip() if date_match else datetime.now().strftime("%Y-%m-%d")
        date_confidence = 0.9 if date_match else 0.3

        due_date_match = self.due_date_pattern.search(text)
        due_date = due_date_match.group(1).strip() if due_date_match else "Net 30"

        # 4. Tax ID
        tax_id_match = self.tax_id_pattern.search(text)
        tax_id = tax_id_match.group(1).strip() if tax_id_match else "N/A"
        tax_id_confidence = 0.95 if tax_id_match else 0.4

        # 5. Currency
        currency = self._detect_currency(text)

        # 6. Financial Amounts
        total_match = self.total_pattern.search(text)
        grand_total = self._clean_amount(total_match.group(1)) if total_match else 0.0
        total_confidence = 0.95 if total_match else 0.2

        subtotal_match = self.subtotal_pattern.search(text)
        subtotal = self._clean_amount(subtotal_match.group(1)) if subtotal_match else 0.0

        tax_match = self.tax_pattern.search(text)
        tax_amount = self._clean_amount(tax_match.group(1)) if tax_match else 0.0

        # 7. Line Items
        line_items = self.extract_line_items(text)
        items_sum = round(sum(item['total'] for item in line_items), 2)

        # Reconciliation: If subtotal missing, infer from line items or total
        if subtotal == 0.0:
            if items_sum > 0:
                subtotal = items_sum
            elif grand_total > 0 and tax_amount > 0:
                subtotal = round(grand_total - tax_amount, 2)
            elif grand_total > 0:
                subtotal = grand_total

        if grand_total == 0.0:
            grand_total = round(subtotal + tax_amount, 2)

        # 8. Mathematical Verification
        # Check: Subtotal + Tax == Grand Total
        expected_total = round(subtotal + tax_amount, 2)
        math_matches = abs(expected_total - grand_total) <= 0.05
        
        # Check: Sum of Line Items == Subtotal
        items_match_subtotal = (len(line_items) == 0) or (abs(items_sum - subtotal) <= 0.05)

        # Overall Confidence Score Calculation
        weights = [vendor_confidence, inv_confidence, date_confidence, total_confidence, tax_id_confidence]
        if math_matches:
            weights.append(1.0)
        else:
            weights.append(0.3)
            
        overall_confidence_pct = round((sum(weights) / len(weights)) * 100, 1)

        # File hash for deduplication
        file_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

        return {
            "filename": filename or "raw_text_entry.txt",
            "file_hash": file_hash,
            "vendor": vendor,
            "vendor_confidence": round(vendor_confidence, 2),
            "invoice_number": invoice_number,
            "invoice_number_confidence": round(inv_confidence, 2),
            "date": invoice_date,
            "date_confidence": round(date_confidence, 2),
            "due_date": due_date,
            "tax_id": tax_id,
            "tax_id_confidence": round(tax_id_confidence, 2),
            "currency": currency,
            "subtotal": round(subtotal, 2),
            "tax": round(tax_amount, 2),
            "total": round(grand_total, 2),
            "total_confidence": round(total_confidence, 2),
            "line_items": line_items,
            "math_reconciled": math_matches,
            "items_reconciled": items_match_subtotal,
            "confidence_score": overall_confidence_pct,
            "status": "APPROVED" if (overall_confidence_pct >= 85 and math_matches) else "REVIEW_REQUIRED"
        }

    def process_file(self, file_path: str) -> Dict[str, Any]:
        """Extracts text from PDF (using pypdf) or plain text file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = os.path.basename(file_path)
        content = ""

        if file_path.lower().endswith('.pdf'):
            try:
                import pypdf
                reader = pypdf.PdfReader(file_path)
                pages_text = []
                for p in reader.pages:
                    extract = p.extract_text()
                    if extract:
                        pages_text.append(extract)
                content = "\n".join(pages_text)
            except Exception as e:
                # Fallback to PyMuPDF if installed
                try:
                    import fitz
                    doc = fitz.open(file_path)
                    content = "\n".join([page.get_text() for page in doc])
                    doc.close()
                except Exception:
                    raise RuntimeError(f"Failed to extract PDF text: {str(e)}")
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

        return self.extract_from_text(content, filename)
