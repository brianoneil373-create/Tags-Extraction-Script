import re
import unicodedata
import pandas as pd
import pdfplumber
import streamlit as st

st.set_page_config(page_title="Bosta Tag Extractor", layout="wide")


def clean_bidi_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", text)
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    ascii_digits = "0123456789"
    return text.translate(str.maketrans(arabic_digits, ascii_digits))


def extract_bosta_data(pdf_file):
    rows = []

    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                # 1. Full text for SKUs, Order Reference, and Shipment ID
                raw_text = page.extract_text() or ""
                text = clean_bidi_text(raw_text)

                name_match = re.search(r"trimize:#(\d+)", text)
                name = name_match.group(1) if name_match else ""

                shipment_id_match = re.search(
                    r"Tracking Number\s*(\d+)", text
                )
                if not shipment_id_match:
                    shipment_id_match = re.search(
                        r"(\d{8,11})\s*\n?\s*Order Reference:", text
                    )
                if not shipment_id_match:
                    shipment_id_match = re.search(r"\b(\d{9,10})\b", text)
                shipment_id = (
                    shipment_id_match.group(1) if shipment_id_match else ""
                )

                # 2. Extract COD Amount via Word Coordinates (Spatial Proximity)
                words = page.extract_words()
                for w in words:
                    w["text"] = clean_bidi_text(w["text"])

                total = 0.0
                financial_status = "Paid"

                # Locate the anchor word 'التحصيل' or 'COD'
                anchors = [
                    w
                    for w in words
                    if any(
                        kw in w["text"] for kw in ["التحصيل", "مبلغ", "Cash"]
                    )
                ]

                if anchors:
                    # Target the first anchor found (header COD box)
                    anchor = anchors[0]

                    # Filter for words on the same horizontal band (+/- 15 points vertically)
                    same_line_words = [
                        w
                        for w in words
                        if abs(w["top"] - anchor["top"]) <= 15
                    ]

                    # Sort words horizontally from left to right
                    same_line_words = sorted(
                        same_line_words, key=lambda x: x["x0"]
                    )
                    line_string = " ".join([w["text"] for w in same_line_words])

                    # Glue numbers split by commas/spaces like "1, 549" or "1,549" -> "1549"
                    line_string = re.sub(
                        r"(\d+)\s*,\s*(\d+)", r"\1\2", line_string
                    )

                    if "لا يوجد" in line_string:
                        total = 0.0
                        financial_status = "Paid"
                    else:
                        # Extract all clean digit sequences on that exact line
                        digit_matches = re.findall(r"\b\d+(?:\.\d+)?\b", line_string)
                        
                        # Exclude 4-digit years (2024-2030) or ID matches
                        valid_nums = [
                            float(n)
                            for n in digit_matches
                            if n not in [name, shipment_id]
                            and not (2020 <= float(n) <= 2030)
                        ]

                        if valid_nums:
                            total = valid_nums[0]  # First price number on that line
                            financial_status = (
                                "Pending" if total > 0 else "Paid"
                            )
                else:
                    # General fallback across full page text
                    clean_full = re.sub(r"(\d+)\s*,\s*(\d+)", r"\1\2", text)
                    if "لا يوجد" in clean_full:
                        total = 0.0
                        financial_status = "Paid"
                    else:
                        cod_fallback = re.search(
                            r"(\d+(?:\.\d+)?)\s*(?:ج\.?م|EGP)", clean_full
                        )
                        if cod_fallback:
                            total = float(cod_fallback.group(1))
                            financial_status = (
                                "Pending" if total > 0 else "Paid"
                            )

                # 3. Lineitem SKU & Quantity Extraction
                skus_found = re.findall(
                    r"x\s*(\d+)\s*\(?([A-Z0-9\-]+)\)?", text
                )

                if skus_found:
                    for qty, sku in skus_found:
                        rows.append(
                            {
                                "Name": name,
                                "Financial Status": financial_status,
                                "Total": total,
                                "Lineitem sku": sku,
                                "Lineitem quantity": int(qty),
                                "Shipment ID": shipment_id,
                            }
                        )
                else:
                    rows.append(
                        {
                            "Name": name,
                            "Financial Status": financial_status,
                            "Total": total,
                            "Lineitem sku": "",
                            "Lineitem quantity": 1,
                            "Shipment ID": shipment_id,
                        }
                    )

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
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
