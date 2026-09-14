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

                # 1. Extract Order Reference / Name (e.g. 120107)
                name_match = re.search(r'Order Reference:\s*trimize:#(\d+)', text)
                name = name_match.group(1) if name_match else ""

                # 2. Extract Shipment ID (Tracking Number)
                shipment_id_match = re.search(r'Tracking Number\s*(\d+)', text)
                if not shipment_id_match:
                    shipment_id_match = re.search(r'(\d{8,11})\s*\n?\s*Order Reference:', text)
                if not shipment_id_match:
                    shipment_id_match = re.search(r'\b(\d{9,10})\b', text)
                shipment_id = shipment_id_match.group(1) if shipment_id_match else ""

                # 3. Robust Cash / COD Amount Extraction
                total = 0.0
                financial_status = "Paid"

                if "لا يوجد" in text:
                    total = 0.0
                    financial_status = "Paid"
                else:
                    # Look for currency prefix pattern e.g. "ج.م1,549" or "ج.م999"
                    cod_match = re.search(r'ج\.م\s*([0-9,]+(?:\.[0-9]+)?)', text)
                    if not cod_match:
                        cod_match = re.search(r'([0-9,]+(?:\.[0-9]+)?)\s*ج\.م', text)

                    if cod_match:
                        clean_str = cod_match.group(1).replace(',', '')
                        total = float(clean_str)
                        if total > 0:
                            financial_status = "Pending"

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
