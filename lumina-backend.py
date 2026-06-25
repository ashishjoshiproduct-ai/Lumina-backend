from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import io
import traceback

app = Flask(__name__)
CORS(app)

def extract_text_from_pdf(pdf_bytes):
    """Extract text from PDF using pdfplumber."""
    try:
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception as e:
        raise ValueError(f"Could not open PDF: {str(e)}")
    
    all_text = []
    
    for page_num, page in enumerate(pdf.pages):
        try:
            # Try standard text extraction
            text = page.extract_text()
            
            if text and text.strip():
                all_text.append(text)
            else:
                # Fallback: try layout mode
                text = page.extract_text(layout=True)
                if text and text.strip():
                    all_text.append(text)
        except Exception as e:
            # Skip pages that fail
            continue
    
    pdf.close()
    
    if not all_text:
        raise ValueError("No text could be extracted from this PDF")
    
    return "\n\n".join(all_text)

@app.route("/extract", methods=["POST"])
def extract():
    """Extract text from uploaded PDF."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    
    try:
        pdf_bytes = file.read()
        text = extract_text_from_pdf(pdf_bytes)
        
        return jsonify({
            "status": "success",
            "text": text,
            "filename": file.filename
        })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "trace": traceback.format_exc()
        }), 400

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
