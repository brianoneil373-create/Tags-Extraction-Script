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

                # 1. Extract Order Reference / Name
                name_match = re.search(r'Order Reference:\s*trimize:#(\d+)', text)
                name = name_match.group(1) if name_match else ""

                # 2. Extract Shipment ID (Tracking Number)
                shipment_id_match = re.search(r'(\d{9,10})\s*\n?\s*Order Reference:', text)
                if not shipment_id_match:
                    shipment_id_match = re.search(r'\b(\d{9,10})\b', text)
                shipment_id = shipment_id_match.group(1) if shipment_id_match else ""

                # 3. Extract COD Amount / Financial Status via Table Extraction
                total = 0.0
                financial_status = "Paid"

                # Pull all structured tables from the tag page
                tables = page.extract_tables() or []
                found_cod = False

                for table in tables:
                    for row in table:
                        row_text = " ".join([str(cell) for cell in row if cell])
                        # Bosta labels cash amounts near COD / Cash / التحصيل / ج.م
                        if any(kw in row_text for kw in ["مبلغ", "التحصيل", "ج.م", "COD", "Cash"]):
                            # Extract all numbers from this table row
                            nums = re.findall(r'(\d+(?:[\.,]\d+)?)', row_text)
                            for num in nums:
                                clean_num = float(num.replace(',', ''))
                                # Exclude tracking ID and order reference from total
                                if clean_num > 0 and num not in [name, shipment_id]:
                                    total = clean_num
                                    financial_status = "Pending"
                                    found_cod = True
                                    break
                        if found_cod:
                            break
                    if found_cod:
                        break

                # Fallback: Search full page text if table extraction missed it
                if not found_cod:
                    cod_matches = re.findall(r'(\d+(?:\.\d+)?)\s*ج\.م', text)
                    if cod_matches:
                        total = float(cod_matches[0])
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
st.write("Upload your Bosta PDF airway bills below.")

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
    else:
        st.warning("No data could be extracted from the uploaded PDF.")
