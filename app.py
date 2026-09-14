import re
import pandas as pd
import pdfplumber
import streamlit as st

st.set_page_config(page_title="Bosta Tag Extractor", layout="wide")

def extract_bosta_data(pdf_file):
    rows = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            # 1. Extract Name (Order Reference number e.g. 120107)
            name_match = re.search(r'Order Reference:\s*trimize:#(\d+)', text)
            name = name_match.group(1) if name_match else ""

            # 2. Extract Shipment ID (9-10 digit tracking number directly above Order Reference)
            shipment_id_match = re.search(r'(\d{9,10})\s*\n?\s*Order Reference:', text)
            if not shipment_id_match:
                shipment_id_match = re.search(r'Customer Notes:.*?\n\s*(\d{9,10})', text, re.DOTALL)
            shipment_id = shipment_id_match.group(1) if shipment_id_match else ""

            # 3. Extract Financial Status & Total
            cod_section = ""
            for line in text.split('\n'):
                if "مبلغ" in line or "التحصيل" in line or "ج.م" in line:
                    cod_section += " " + line

            numbers = re.findall(r'(\d+(?:[\.,]\d+)?)', cod_section)
            clean_numbers = [n.replace(',', '') for n in numbers]

            if clean_numbers and "لا يوجد" not in cod_section:
                financial_status = "Pending"
                total = float(clean_numbers[0])
            else:
                financial_status = "Paid"
                total = 0.0

            # 4. Extract Lineitem SKU and Quantity
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

    return pd.DataFrame(rows)

# --- Streamlit UI ---
st.title("Bosta Shipment Tag Extractor")
st.write("Upload your Bosta PDF airway bills below to generate your Excel summary.")

uploaded_file = st.file_uploader("Upload Bosta PDF Airway Bills", type=["pdf"])

if uploaded_file is not None:
    with st.spinner("Processing PDF..."):
        df = extract_bosta_data(uploaded_file)
        
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
