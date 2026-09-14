import re
import unicodedata
import pandas as pd
import pdfplumber
import streamlit as st

st.set_page_config(page_title="Bosta Tag Extractor", layout="wide")


def clean_bidi_text(text: str) -> str:
    if not text:
        return ""
    # Remove BiDi control characters
    text = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", text)
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    ascii_digits = "0123456789"
    return text.translate(str.maketrans(arabic_digits, ascii_digits))


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

                # 3. Direct Header Extraction for "مبلغ التحصيل"
                total = 0.0
                financial_status = "Paid"

                # Grab the line containing "مبلغ التحصيل" or "Cash Amount"
                cod_line_match = re.search(
                    r"(?:مبلغ التحصيل|Cash Amount|COD):?\s*([^\n]+)", text
                )

                if cod_line_match:
                    cod_val_str = cod_line_match.group(1).strip()

                    if "لا يوجد" in cod_val_str or "Paid" in cod_val_str:
                        total = 0.0
                        financial_status = "Paid"
                    else:
                        # Normalize commas inside digits (e.g. converts "1, 549" or "1,549" to "1549")
                        # This fixes the issue where 1,549 was getting split into 1 and 549!
                        digits_combined = re.sub(
                            r"(\d+)\s*,\s*(\d+)", r"\1\2", cod_val_str
                        )
                        price_match = re.search(
                            r"(\d+(?:\.\d+)?)", digits_combined
                        )

                        if price_match:
                            total = float(price_match.group(1))
                            financial_status = (
                                "Pending" if total > 0 else "Paid"
                            )
                else:
                    # Fallback if line match isn't triggered
                    if "لا يوجد" in text:
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
