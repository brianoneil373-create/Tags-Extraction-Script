import re
import pandas as pd
import pdfplumber
import streamlit as st

st.set_page_config(page_title="Bosta Tag Extractor", layout="wide")

def extract_bosta_data(pdf_file):
    rows = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                words = page.extract_words()

                # 1. Extract Order Reference / Name (e.g. 120107)
                name_match = re.search(r'Order Reference:\s*trimize:#(\d+)', text)
                name = name_match.group(1) if name_match else ""

                # 2. Extract Shipment ID (Tracking Number)
                shipment_id_match = re.search(r'(\d{9,10})\s*\n?\s*Order Reference:', text)
                if not shipment_id_match:
                    shipment_id_match = re.search(r'\b(\d{9,10})\b', text)
                shipment_id = shipment_id_match.group(1) if shipment_id_match else ""

                # 3. Coordinate-Based COD Amount Extraction
                # Find words on the page matching Arabic cash labels
                total = 0.0
                financial_status = "Paid"
                
                # Filter all words containing numeric/decimal values on the page
                numeric_words = [w for w in words if re.search(r'^\d+(?:[\.,]\d+)?$', w['text'])]
                
                # Locate the vertical position (top/bottom) of Arabic COD keywords
                cod_y_positions = [
                    w['top'] for w in words 
                    if any(kw in w['text'] for kw in ["مبلغ", "التحصيل", "الجام", "ج.م"])
                ]

                if cod_y_positions:
                    # Look for numeric words sitting on the same horizontal line (within 15 vertical pixels)
                    target_y = cod_y_positions[0]
                    line_numbers = [
                        w['text'] for w in numeric_words 
                        if abs(w['top'] - target_y) < 15 and w['text'] not in [name, shipment_id]
                    ]
                    
                    if line_numbers:
                        clean_val = float(line_numbers[0].replace(',', ''))
                        if clean_val > 0:
                            total = clean_val
                            financial_status = "Pending"

                # Fallback: Search all extracted text for decimal prices (e.g., 999.00 or 899.5)
                if total == 0.0:
                    price_matches = re.findall(r'\b(\d{2,5}(?:\.\d{1,2})?)\b', text)
                    for price in price_matches:
                        if price not in [name, shipment_id]:
                            val = float(price)
                            # Exclude typical quantities/year digits
                            if 20 < val < 50000:
                                total = val
                                financial_status = "Pending"
                                break

                # 4. Extract Lineitem SKU & Quantity
                skus_found = re.findall(r'x\s*(\d+)\s*\(?([A-Z0-9\-]+)\)?', text)

                if skus_found:
                    for qty, sku in skus_found:
                        rows.append({
                            "Name": name,
                            "Financial Status": financial_status,
                            "Total": total,
                            "Lineitem sku": sku,
                            "Lineitem quantity": int(qty),
                            "Shipment ID": shipment_id
                        })
                else:
                    rows.append({
                        "Name": name,
                        "Financial Status": financial_status,
                        "Total": total,
                        "Lineitem sku": "",
                        "Lineitem quantity": 1,
                        "Shipment ID": shipment_id
                    })

    except Exception as e:
        st.error(f"Error processing PDF file: {str(e)}")

    return pd.DataFrame(rows)

# --- Streamlit UI ---
st.title("Bosta Shipment Tag Extractor")
uploaded_file = st.file_uploader("Upload Bosta PDF Airway Bills", type=["pdf"])

if uploaded_file is not None:
    with st.spinner("Processing PDF..."):
        df = extract_bosta_data(uploaded_file)
        
    if not df.empty:
        st.success("Extraction complete!")
        st.dataframe(df, use_container_width=True)

        output_name = "bosta_extracted_data.xlsx"
        df.to_excel(output_name, index=False)
        
        with open(output_name, "rb") as file:
            st.download_button(
                label="Download Excel File",
                data=file,
                file_name=output_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
