"""
InvoiceFlow — SQLite Persistence & Audit Trail Engine
Handles storage, deduplication, review status updates, and audit logging.
"""

import sqlite3
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "invoiceflow.db")

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = DB_PATH):
    """Initializes tables for invoices, line items, and audit logs."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_hash TEXT,
        filename TEXT NOT NULL,
        vendor TEXT NOT NULL,
        invoice_number TEXT NOT NULL,
        date TEXT,
        due_date TEXT,
        currency TEXT DEFAULT 'USD',
        subtotal REAL DEFAULT 0.0,
        tax REAL DEFAULT 0.0,
        total REAL NOT NULL,
        confidence_score REAL,
        status TEXT DEFAULT 'PENDING_REVIEW',
        math_reconciled INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS line_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        description TEXT NOT NULL,
        quantity INTEGER DEFAULT 1,
        unit_price REAL DEFAULT 0.0,
        total REAL NOT NULL,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER,
        action TEXT NOT NULL,
        details TEXT,
        performed_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()

def check_duplicate(invoice_number: str, file_hash: Optional[str] = None, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Checks if an invoice number or file hash already exists in the database."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    
    if invoice_number and invoice_number != "INV-UNKNOWN":
        cur.execute("SELECT * FROM invoices WHERE invoice_number = ? ORDER BY id DESC LIMIT 1", (invoice_number,))
        row = cur.fetchone()
        if row:
            conn.close()
            return dict(row)

    if file_hash:
        cur.execute("SELECT * FROM invoices WHERE file_hash = ? ORDER BY id DESC LIMIT 1", (file_hash,))
        row = cur.fetchone()
        if row:
            conn.close()
            return dict(row)

    conn.close()
    return None

def save_invoice(data: Dict[str, Any], db_path: str = DB_PATH) -> int:
    """Saves invoice and line items with transaction safety and audit entry."""
    init_db(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO invoices (
        file_hash, filename, vendor, invoice_number, date, due_date, 
        currency, subtotal, tax, total, confidence_score, status, math_reconciled
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("file_hash", ""),
        data.get("filename", "unknown"),
        data.get("vendor", "Unknown Vendor"),
        data.get("invoice_number", "INV-UNKNOWN"),
        data.get("date", ""),
        data.get("due_date", ""),
        data.get("currency", "USD"),
        data.get("subtotal", 0.0),
        data.get("tax", 0.0),
        data.get("total", 0.0),
        data.get("confidence_score", 0.0),
        data.get("status", "PENDING_REVIEW"),
        1 if data.get("math_reconciled", True) else 0
    ))
    
    invoice_id = cur.lastrowid

    # Insert Line Items
    line_items = data.get("line_items", [])
    for item in line_items:
        cur.execute("""
        INSERT INTO line_items (invoice_id, description, quantity, unit_price, total)
        VALUES (?, ?, ?, ?, ?)
        """, (
            invoice_id,
            item.get("description", "Item"),
            item.get("quantity", 1),
            item.get("unit_price", 0.0),
            item.get("total", 0.0)
        ))

    # Audit log
    cur.execute("""
    INSERT INTO audit_logs (invoice_id, action, details)
    VALUES (?, ?, ?)
    """, (
        invoice_id,
        "INGESTED",
        f"Extracted with confidence {data.get('confidence_score', 0)}%"
    ))

    conn.commit()
    conn.close()
    return invoice_id

def update_status(invoice_id: int, new_status: str, notes: str = "", db_path: str = DB_PATH) -> bool:
    """Updates invoice approval/review status and writes audit log."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE invoices SET status = ? WHERE id = ?", (new_status, invoice_id))
    cur.execute("""
    INSERT INTO audit_logs (invoice_id, action, details)
    VALUES (?, ?, ?)
    """, (invoice_id, f"STATUS_CHANGE_{new_status}", notes))
    conn.commit()
    conn.close()
    return True

def get_all_invoices(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves all invoices ordered by latest first."""
    init_db(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM invoices ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_summary_stats(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Computes accounting dashboard summary statistics."""
    init_db(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*), SUM(total), AVG(confidence_score) FROM invoices")
    count, total_sum, avg_conf = cur.fetchone()
    
    cur.execute("SELECT COUNT(*) FROM invoices WHERE status = 'APPROVED'")
    approved_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM invoices WHERE status = 'REVIEW_REQUIRED' OR math_reconciled = 0")
    flagged_count = cur.fetchone()[0]

    conn.close()
    return {
        "total_invoices": count or 0,
        "total_value": round(total_sum or 0.0, 2),
        "average_confidence": round(avg_conf or 0.0, 1),
        "approved_count": approved_count or 0,
        "flagged_count": flagged_count or 0
    }
