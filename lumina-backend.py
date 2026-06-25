from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import io
import traceback

app = Flask(__name__)
CORS(app)

def extract_text_from_pdf(pdf_bytes):
    """Extract text from PDF using pdfplumber with column-aware sorting."""
    try:
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception as e:
        raise ValueError(f"Could not open PDF: {str(e)}")
    
    all_text = []
    
    for page_num, page in enumerate(pdf.pages):
        try:
            pw = page.width
            mid = pw / 2
            
            # Extract all text with position info
            text_dict = page.extract_text_dict()
            if not text_dict or "text_dict" not in text_dict:
                continue
            
            text_blocks = text_dict.get("text_dict", [])
            if not text_blocks:
                continue
            
            left_blocks = []
            right_blocks = []
            full_blocks = []
            
            for block in text_blocks:
                bbox = block.get("bbox", [])
                if len(bbox) < 4:
                    continue
                
                x0, y0, x1, y1 = bbox
                text = block.get("text", "").strip()
                
                if len(text) < 3:
                    continue
                
                # Skip very short text (likely diagram labels)
                lines = text.split("\n")
                avg_line_len = sum(len(l) for l in lines) / max(len(lines), 1)
                if avg_line_len < 20 and len(lines) <= 2 and len(text) < 50:
                    continue
                
                block_width = x1 - x0
                if block_width > pw * 0.6:  # full width
                    full_blocks.append((y0, text))
                elif x0 + block_width / 2 < mid:  # left column
                    left_blocks.append((y0, text))
                else:  # right column
                    right_blocks.append((y0, text))
            
            # Sort by vertical position
            full_blocks.sort(key=lambda b: b[0])
            left_blocks.sort(key=lambda b: b[0])
            right_blocks.sort(key=lambda b: b[0])
            
            # Separate full-width header from footer
            body_start_y = min(
                (left_blocks[0][0] if left_blocks else 999),
                (right_blocks[0][0] if right_blocks else 999)
            )
            
            header = [(y, t) for y, t in full_blocks if y < body_start_y]
            footer = [(y, t) for y, t in full_blocks if y >= body_start_y]
            
            # Combine: header + left col + right col + footer
            ordered = header + left_blocks + right_blocks + footer
            page_text = "\n\n".join(t for _, t in ordered)
            
            if page_text.strip():
                all_text.append(page_text)
        except Exception as e:
            # Skip this page if extraction fails
            continue
    
    pdf.close()
    return "\n\n---PAGE BREAK---\n\n".join(all_text)

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
