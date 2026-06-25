from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz
import traceback

app = Flask(__name__)
CORS(app)

def extract_text_from_pdf(pdf_bytes):
    """Extract text from PDF using PyMuPDF with column-aware sorting."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Could not open PDF: {str(e)}")
    
    all_text = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        pw = page.rect.width
        mid = pw / 2
        
        try:
            d = page.get_text("dict", sort=True)
        except:
            continue
        
        # Find image areas to filter out diagram labels
        image_areas = []
        for block in d["blocks"]:
            if block["type"] == 1:
                image_areas.append(fitz.Rect(block["bbox"]))
        
        left_blocks = []
        right_blocks = []
        full_blocks = []
        
        for block in d["blocks"]:
            if block["type"] == 1:  # image
                continue
            
            x0, y0, x1, y1 = block["bbox"]
            block_rect = fitz.Rect(block["bbox"])
            
            # Skip if overlaps with image area
            in_image = False
            for img_rect in image_areas:
                overlap = block_rect & img_rect
                if not overlap.is_empty:
                    overlap_ratio = overlap.get_area() / max(block_rect.get_area(), 1)
                    if overlap_ratio > 0.3:
                        in_image = True
                        break
            if in_image:
                continue
            
            # Extract text from block
            lines_text = []
            sizes = []
            for line in block["lines"]:
                lt = ""
                for span in line["spans"]:
                    lt += span["text"]
                    if "size" in span:
                        sizes.append(span["size"])
                lt = lt.strip()
                if lt:
                    lines_text.append(lt)
            
            text = " ".join(lines_text).strip()
            if len(text) < 3:
                continue
            
            # Skip likely diagram labels
            avg_line_len = sum(len(l) for l in lines_text) / max(len(lines_text), 1)
            if avg_line_len < 25 and len(lines_text) <= 3 and len(text) < 60:
                continue
            
            # Classify by position
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
    
    doc.close()
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
