# Security Policy: InvoiceFlow-automation

## 1. Supported Versions
| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | :white_check_mark: |
| < 2.0   | :x:                |

## 2. Threat Model & Mitigations

### Input Validation & File Handling
- **MIME Type & Magic Number Verification:** Uploads are strictly checked against allowed types (`application/pdf`, `text/plain`, `text/csv`).
- **File Size Limits:** Maximum upload payload is capped at 10 MB to prevent denial-of-service (DoS) via decompression bombs or unbounded memory allocation.
- **Path Traversal Prevention:** All uploaded filenames are sanitized using secure basename extraction; files are processed in isolated temporary directories.

### Data Privacy & Regulatory Compliance
- **Financial Information Protection:** Extracted records, tax IDs, and vendor bank identifiers are persisted solely in the local SQLite database (`invoiceflow.db`) and never transmitted to third-party tracking services.
- **Data Deletion:** Temporary invoice files generated during extraction are purged immediately upon processing completion.

### Arithmetic & Data Integrity Controls
- **Reconciliation Check:** Mathematical verification ensures `Subtotal + Tax == Grand Total` with an epsilon tolerance of $0.05. Any discrepancy triggers a `REVIEW_REQUIRED` status to protect financial ledgers from arithmetic corruption.
- **Cryptographic Hashing:** Every invoice payload is fingerprinted using SHA-256 for instant duplicate detection.

## 3. Reporting a Vulnerability
To report a security vulnerability or sensitive data exposure issue, please submit an issue or contact the repository owner at `sharmika.murugesan@gmail.com`. Disclosures will be acknowledged within 24 hours.
