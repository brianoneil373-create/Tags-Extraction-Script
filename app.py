import re
import pandas as pd
import pdfplumber
import streamlit as st

def extract_bosta_data(pdf_file):
    rows = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            # 1. Extract Name (Order Reference number)
            name_match = re.search(r'Order Reference:\s*trimize:#(\d+)', text)
            name = name_match.group(1) if name_match else ""

            # 2. Extract Shipment ID (Tracking Number)
            shipment_id_match = re.search(r'Tracking Number\s*\n.*?\n(\d+)', text)
            if not shipment_id_match:
                shipment_id_match = re.search(r'(\d{9,12})\s*\nOrder Reference:', text)
            shipment_id = shipment_id_match.group(1) if shipment_id_match else ""

            # 3. Extract Financial Status & Total
            cod_match = re.search(r'مبلغ التحصيل:\s*([^\n]+)', text)
            financial_status = "Paid"
            total = 0.0

            if cod_match:
                raw_cod = cod_match.group(1).replace(',', '').strip()
                # Find digits or decimal numbers in the COD text
                num_match = re.search(r'(\d+(?:\.\d+)?)', raw_cod)
                if num_match:
                    financial_status = "Pending"
                    total = float(num_match.group(1))

            # 4. Extract Lineitem SKU and Quantity
            # Pattern extracts quantity 'x 1' and SKU inside brackets/parentheses '(TRZ-XXX-XXX)'
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
                # Fallback if SKU structure isn't matched
                rows.append({
                    "Name": name,
                    "Financial Status": financial_status,
                    "Total": total,
                    "Lineitem sku": "",
                    "Lineitem quantity": 1,
                    "Shipment ID": shipment_id
                })

    return pd.DataFrame(rows)

# Streamlit User Interface
st.title("Bosta Shipment Tag Extractor")

uploaded_file = st.file_uploader("Upload Bosta PDF Airway Bills", type=["pdf"])

if uploaded_file is not None:
    df = extract_bosta_data(uploaded_file)
    st.write("### Extracted Data Preview", df)

    # Convert dataframe to Excel format for download
    output_name = "bosta_extracted_data.xlsx"
    df.to_excel(output_name, index=False)
    
    with open(output_name, "rb") as file:
        st.download_button(
            label="Download Excel File",
            data=file,
            file_name=output_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
