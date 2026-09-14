import re
import pandas as pd
import pypdf
import streamlit as st

st.set_page_config(page_title="Shipment Tag Reviewer", layout="wide")

def clean_description(text):
    if not text:
        return ""
    
    # 1. Strip curly braces, bullet points, and separator bars
    text = re.sub(r'[\{\}\bullet|]', '', text)
    
    # 2. Remove Arabic letters and diacritics
    text = re.sub(r'[\u0600-\u06FF]', '', text)
    
    # 3. If there is a closing parenthesis (e.g. end of SKU code), crop any stray trailing text after it
    if ')' in text:
        text = text[:text.rfind(')') + 1]
        
    # 4. Clean up trailing/leading whitespace and double spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

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
        cod_match = re.search(r'ج\.م\s*([\d,]+)', text)
        if cod_match:
            cod_amount = cod_match.group(1).replace(',', '')

        # 4. Phone Number
        phone = None
        phone_match = re.search(r'(20\d{10}|\+?20\d{10})', text)
        if phone_match:
            phone = phone_match.group(1)

        # 5. Product Description
        item_desc = None
        lines = text.split('\n')
        for line in lines:
            if any(keyword in line for keyword in ["TRZ-", "Bundle", "Routine"]):
                # Clean the extracted line before saving
                item_desc = clean_description(line)
                break

        records.append({
            "Page": idx,
            "Order Reference": order_ref,
            "Tracking Number": tracking_num,
            "Phone": phone,
            "COD Amount (EGP)": cod_amount,
            "Description": item_desc
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
