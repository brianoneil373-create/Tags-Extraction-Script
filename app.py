import re
import unicodedata
import pandas as pd
import pdfplumber
import streamlit as st

st.set_page_config(page_title="Bosta Tag Extractor", layout="wide")


def clean_bidi_text(text: str) -> str:
    if not text:
        return ""
    # Strip BiDi control characters
    text = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", text)
    # Convert Arabic-Indic digits (٠-٩) to standard ASCII (0-9)
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    ascii_digits = "0123456789"
    text = text.translate(str.maketrans(arabic_digits, ascii_digits))
    return unicodedata.normalize("NFKD", text)


def extract_bosta_data(pdf_file):
    rows = []

    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = clean_bidi_text(page.extract_text() or "")

                # 1. Order Reference / Name
                name_match = re.search(r"trimize:#(\d+)", text)
                name = name_match.group(1) if name_match else ""

                # 2. Shipment ID
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

                # 3. COD Extraction Strategy
                total = 0.0
                financial_status = "Paid"

                # Join digit groupings split by commas/spaces (e.g., "1, 549" or "1,549" -> "1549")
                normalized_text = re.sub(r"(\d+)\s*,\s*(\d+)", r"\1\2", text)

                # Check for explicit "No COD" / "Paid" indicators first
                if "لا يوجد" in normalized_text:
                    total = 0.0
                    financial_status = "Paid"
                else:
                    # Look for currency matches: "999ج.م", "999 ج.م", "ج.م999", "1549 EGP", etc.
                    cod_match = re.search(
                        r"(\d+(?:\.\d+)?)\s*(?:ج\.?م|EGP)", normalized_text
                    )
                    if not cod_match:
                        cod_match = re.search(
                            r"(?:ج\.?م|EGP)\s*(\d+(?:\.\d+)?)", normalized_text
                        )

                    # Fallback: find any number on the same line as 'التحصيل' or 'مبلغ'
                    if not cod_match:
                        cod_line = re.search(
                            r".*(?:التحصيل|مبلغ|COD).*", normalized_text
                        )
                        if cod_line:
                            cod_match = re.search(
                                r"(\d+(?:\.\d+)?)", cod_line.group(0)
                            )

                    if cod_match:
                        try:
                            val = float(cod_match.group(1))
                            # Ignore shipment/order IDs accidentally caught as price
                            if str(int(val)) not in [name, shipment_id]:
                                total = val
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
