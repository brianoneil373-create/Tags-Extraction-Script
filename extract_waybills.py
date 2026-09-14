import re
import pandas as pd
import pdfplumber
import streamlit as st

# 1. Define the PDF parsing function
def parse_bosta_pdf(pdf_file):
    records = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(layout=False) or ""
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # Order Reference
            order_ref = None
            ref_match = re.search(r'Order Reference:\s*(trimize:#\d+|\S+)', text)
            if ref_match:
                order_ref = ref_match.group(1)
            
            # Tracking Number
            tracking_num = None
            track_match = re.search(r'(\b\d{9,10}\b)', text)
            if track_match:
                tracking_num = track_match.group(1)
                
            # Customer Name & Phone
            name, phone = None, None
            for idx, line in enumerate(lines):
                if "توصيل إلى:" in line and idx + 2 < len(lines):
                    name = lines[idx + 1]
                    phone_match = re.search(r'(\+?\d{11,13})', lines[idx + 2])
                    if phone_match:
                        phone = phone_match.group(1)
                    break

            # Collection Amount (COD)
            cod_amount = "0"
            cod_match = re.search(r'مبلغ التحصيل:\s*([^\n|]+)', text)
            if cod_match:
                raw_cod = cod_match.group(1).strip()
                if "لا يوجد" in raw_cod:
                    cod_amount = "0.00"
                else:
                    cleaned_cod = re.sub(r'[^\d.]', '', raw_cod)
                    cod_amount = cleaned_cod if cleaned_cod else "0.00"

            # Item Description / Bundle
            item_desc = None
            desc_match = re.search(r'(.*?)\s*\|\s*وصف الشحنة', text)
            if desc_match:
                item_desc = desc_match.group(1).strip()

            records.append({
                "Page": page_num,
                "Order Reference": order_ref,
                "Tracking Number": tracking_num,
                "Customer Name": name,
                "Phone": phone,
                "COD Amount (EGP)": cod_amount,
                "Description": item_desc
            })

    return pd.DataFrame(records)


# 2. Streamlit Web Interface Setup
st.title("Shipment Tag Reviewer")

uploaded_file = st.file_uploader("Upload Airway Bills PDF", type=["pdf"])

if uploaded_file is not None:
    # Process the uploaded file in-memory
    df = parse_bosta_pdf(uploaded_file)
    
    st.success(f"Successfully processed {len(df)} orders!")
    st.dataframe(df)
    
    # Download Button for the processed data
    st.download_button(
        label="Download Data as Excel (CSV)",
        data=df.to_csv(index=False).encode('utf-8-sig'),
        file_name="shipment_summary.csv",
        mime="text/csv"
    )
