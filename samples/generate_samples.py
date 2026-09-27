import os

def create_sample_files(directory: str = "samples"):
    os.makedirs(directory, exist_ok=True)
    
    samples = [
        ("invoice_aws_cloud.txt", """Amazon Web Services Inc.
Invoice Number: INV-9812401
Invoice Date: 2025-01-14
Tax ID: GSTIN-88912A
Bill To: Client Technologies Ltd.

Description: Cloud EC2 & S3 Hosting Services
Period: Dec 2024 - Jan 2025
Amount Due: $1,450.00
Grand Total: $1,450.00
"""),
        ("invoice_google_workspace.txt", """Google Workspace Billing
Invoice #: GOOG-2025-771
Date: 2025-01-20
Tax ID: GSTIN-11223B

Items:
- 25 User Licenses Enterprise Plus
Total Amount: $625.50
Status: Paid via Corporate Card
"""),
        ("invoice_office_supplies.txt", """Apex Office Supplies Co.
INV: APX-44109
Date: 2025-02-02
Tax ID: VAT-991204

Line Items:
- Ergonomic Chairs x 4
- Monitor Mounts x 4
Balance Due: $890.00
""")
    ]
    
    for filename, content in samples:
        path = os.path.join(directory, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

if __name__ == "__main__":
    create_sample_files()
