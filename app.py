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
                full_text = clean_bidi_text(page.extract_text() or "")

                # 1. Order Reference / Name
                name_match = re.search(
                    r"Order Reference:\s*trimize:#(\d+)", full_text
                )
                if not name_match:
                    name_match = re.search(r"trimize:#(\d+)", full_text)
                name = name_match.group(1) if name_match else ""

                # 2. Shipment ID
                shipment_id_match = re.search(
                    r"Tracking Number\s*(\d+)", full_text
                )
                if not shipment_id_match:
                    shipment_id_match = re.search(
                        r"(\d{8,11})\s*\n?\s*Order Reference:", full_text
                    )
                if not shipment_id_match:
                    shipment_id_match = re.search(r"\b(\d{9,10})\b", full_text)
                shipment_id = (
                    shipment_id_match.group(1) if shipment_id_match else ""
                )

                # 3. Geometric Crop for COD Amount
                # Bosta's COD / Amount is always in the bottom-right or middle section.
                # We search words on page to find "التحصيل" or "Cash" anchor coordinates:
                total = 0.0
                financial_status = "Paid"

                words = page.extract_words()
                cod_anchors = [
                    w
                    for w in words
                    if any(
                        kw in w["text"]
                        for kw in ["التحصيل", "مبلغ", "Cash", "COD"]
                    )
                ]

                target_text = ""
                if cod_anchors:
                    # Take the first keyword found and crop a box around it (+/- 50pt Y, full width)
                    anchor = cod_anchors[0]
                    crop_box = (
                        0,
                        max(0, anchor["top"] - 10),
                        page.width,
                        min(page.height, anchor["bottom"] + 40),
                    )
                    cropped_page = page.crop(crop_box)
                    target_text = clean_bidi_text(
                        cropped_page.extract_text() or ""
                    )
                else:
                    target_text = full_text

                # Extract numbers sitting directly near the COD keywords
                nums = re.findall(r"\b\d+(?:\.\d+)?\b", target_text)
                # Filter out the order reference and shipment ID from candidate numbers
                candidate_nums = [
                    float(n)
                    for n in nums
                    if n not in [name, shipment_id] and float(n) < 50000
                ]

                if "لا يوجد" in target_text or "Paid" in target_text:
                    total = 0.0
                    financial_status = "Paid"
                elif candidate_nums:
                    # The price is almost always the largest non-ID number in that row
                    total = max(candidate_nums)
                    financial_status = "Pending" if total > 0 else "Paid"

                # 4. Extract SKUs
                skus_found = re.findall(
                    r"x\s*(\d+)\s*\(?([A-Z0-9\-]+)\)?", full_text
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
