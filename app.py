import re
import pandas as pd
import pypdf
import streamlit as st

st.set_page_config(page_title="Shipment Tag Reviewer", layout="wide")

def parse_bosta_pdf(pdf_file):
    reader = pypdf.PdfReader(pdf_file)
    records = []
    
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        
        # 1. Order Reference
        order_ref = None
        ref_match = re.search(r'Order Reference:\s*(\S+)', text)
        if ref_match:
            order_ref = ref_match.group(1)

        # 2. Tracking Number
        tracking_num = None
        track_match = re.search(r'Tracking Number\s*(\d+)', text)
        if track_match:
            tracking_num = track_match.group(1)

        # 3. COD / Collection Amount
        cod_amount = "0"
        cod_match = re.search(r'مبلغ التحصيل:\s*([\d,]+(?:\.\d+)?)', text)
        if not cod_match:
            cod_match = re.search(r'ج\.م\s*([\d,]+(?:\.\d+)?)', text)
        if cod_match:
            cod_amount = cod_match.group(1).replace(',', '')

        records.append({
            "Page": idx,
            "Order Reference": order_ref,
            "Tracking Number": tracking_num,
            "COD Amount (EGP)": cod_amount
        })

    return pd.DataFrame(records)

# UI Layout
st.title("📦 Shipment Tag Reviewer")

uploaded_file = st.file_uploader("Upload Airway Bills PDF", type=["pdf"])

if uploaded_file is not None:
    try:
        with st.spinner("Processing PDF..."):
            df = parse_bosta_pdf(uploaded_file)
            st.success(f"Processed {len(df)} orders successfully!")
            st.dataframe(df, use_container_width=True)
            
            st.download_button(
                label="📥 Download Data as CSV",
                data=df.to_csv(index=False).encode('utf-8-sig'),
                file_name="shipment_summary.csv",
                mime="text/csv"
            )
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
