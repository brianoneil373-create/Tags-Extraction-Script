import re
import unicodedata
import pandas as pd
import pdfplumber
import streamlit as st

st.set_page_config(page_title="Bosta Tag Extractor", layout="wide")


def clean_bidi_text(text: str) -> str:
    """Removes invisible directional control characters and normalizes Unicode."""
    if not text:
        return ""
    # Remove BiDi control chars (LRM, RLM, LRE, RLE, PDF, LRO, RLO, etc.)
    text = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", text)
    # Convert Arabic-Indic digits (٠-٩) to standard ASCII digits (0-9)
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    ascii_digits = "0123456789"
    trans_table = str.maketrans(arabic_digits, ascii_digits)
    text = text.translate(trans_table)
    # Normalize unicode representations
    return unicodedata.normalize("NFKD", text)


def extract_bosta_data(pdf_file):
    rows = []

    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                raw_text = page.extract_text() or ""
                # Normalize text to fix hidden BiDi marks and Arabic-Indic digits
                text = clean_bidi_text(raw_text)

                # 1. Extract Order Reference / Name (e.g. 120107)
                name_match = re.search(r"Order Reference:\s*trimize:#(\d+)", text)
                name = name_match.group(1) if name_match else ""

                # 2. Extract Shipment ID (Tracking Number)
                shipment_id_match = re.search(r"Tracking Number\s*(\d+)", text)
                if not shipment_id_match:
                    shipment_id_match = re.search(
                        r"(\d{8,11})\s*\n?\s*Order Reference:", text
                    )
                if not shipment_id_match:
                    shipment_id_match = re.search(r"\b(\d{9,10})\b", text)
                shipment_id = (
                    shipment_id_match.group(1) if shipment_id_match else ""
                )

                # 3. Robust COD Amount Extraction
                total = 0.0
                financial_status = "Paid"

                # Check if it's explicitly unpaid/paid by examining the COD context area
                cod_line_match = re.search(
                    r"(?:مبلغ التحصيل|Cash Amount|COD)[^\n]*",
                    text,
                    re.IGNORECASE,
                )
                cod_text = cod_line_match.group(0) if cod_line_match else text

                if "لا يوجد" in cod_text and not re.search(r"\d+", cod_text):
                    total = 0.0
                    financial_status = "Paid"
                else:
                    # Match currency prefix patterns (e.g. "ج.م 1,549" or "1,549 ج.م" or "749ج.م")
                    cod_match = re.search(
                        r"(?:ج\.م|EGP)\s*([0-9,]+(?:\.[0-9]+)?)", text
                    )
                    if not cod_match:
                        cod_match = re.search(
                            r"([0-9,]+(?:\.[0-9]+)?)\s*(?:ج\.م|EGP)", text
                        )

                    if cod_match:
                        clean_str = cod_match.group(1).replace(",", "")
                        try:
                            total = float(clean_str)
                            financial_status = (
                                "Pending" if total > 0 else "Paid"
                            )
                        except ValueError:
                            total = 0.0
                            financial_status = "Paid"

                # 4. Extract Lineitem SKU & Quantity
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
