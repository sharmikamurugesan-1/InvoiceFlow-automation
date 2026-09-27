"""
InvoiceFlow — REST API Server
Provides endpoints for invoice extraction, duplicate verification, approval workflows, and report exports.
"""

import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from extractor import InvoiceExtractor
from database import init_db, save_invoice, check_duplicate, get_all_invoices, update_status, get_summary_stats
from excel_writer import ExcelReportWriter

app = Flask(__name__)
CORS(app)

# Ensure database is ready
init_db()

extractor = InvoiceExtractor()

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "online",
        "service": "InvoiceFlow Processing Engine",
        "version": "2.0.0",
        "capabilities": ["pypdf", "line_item_extraction", "math_reconciliation", "sqlite_audit"]
    })

@app.route('/api/extract', methods=['POST'])
def extract_invoice():
    """Extracts metadata from raw text or uploaded document file."""
    # Check if file uploaded
    if 'file' in request.files:
        uploaded_file = request.files['file']
        if uploaded_file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Save temporarily
        temp_dir = os.path.join(os.path.dirname(__file__), "uploads")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, uploaded_file.filename)
        uploaded_file.save(temp_path)
        
        try:
            result = extractor.process_file(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    else:
        data = request.get_json(force=True, silent=True) or {}
        text = data.get("text", "")
        filename = data.get("filename", "pasted_invoice.txt")
        if not text.strip():
            return jsonify({"error": "No text or file provided"}), 400
        result = extractor.extract_from_text(text, filename)

    # Check for duplicates
    dup = check_duplicate(result.get("invoice_number"), result.get("file_hash"))
    result["is_duplicate"] = (dup is not None)
    if dup:
        result["duplicate_warning"] = f"Warning: Invoice '{result.get('invoice_number')}' already recorded on {dup.get('created_at')}."

    return jsonify(result)

@app.route('/api/invoices', methods=['GET'])
def list_invoices():
    """Returns all persisted invoices from SQLite."""
    invoices = get_all_invoices()
    return jsonify(invoices)

@app.route('/api/invoices/save', methods=['POST'])
def save_reviewed_invoice():
    """Saves human-reviewed invoice to database with audit log."""
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "Invalid payload"}), 400
        
    inv_id = save_invoice(data)
    return jsonify({"success": True, "invoice_id": inv_id, "message": "Invoice persisted successfully."})

@app.route('/api/invoices/<int:inv_id>/status', methods=['POST'])
def change_status(inv_id: int):
    """Updates approval status (APPROVED, FLAGGED, REJECTED)."""
    data = request.get_json(force=True) or {}
    new_status = data.get("status", "APPROVED")
    notes = data.get("notes", "")
    update_status(inv_id, new_status, notes)
    return jsonify({"success": True, "invoice_id": inv_id, "status": new_status})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Returns analytics dashboard stats."""
    return jsonify(get_summary_stats())

@app.route('/api/export/csv', methods=['GET'])
def export_csv():
    """Generates and downloads the full CSV audit report."""
    invoices = get_all_invoices()
    writer = ExcelReportWriter("invoices_export.csv")
    csv_path = writer.save_report(invoices, export_excel=False)
    return send_file(csv_path, as_attachment=True, download_name="invoices_export.csv")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
