import re
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


def parse_cod_from_text(text: str) -> float:
    """Helper to extract clean COD price from a cell or text line."""
    if not text:
        return 0.0

    text = clean_bidi_text(text)

    if "لا يوجد" in text:
        return 0.0

    # Reunite numbers separated by commas/spaces (e.g. "1, 549" or "1,549" -> "1549")
    text = re.sub(r"(\d+)\s*,\s*(\d+)", r"\1\2", text)

    # Search for all number matches
    matches = re.findall(r"\b\d+(?:\.\d+)?\b", text)

    # Filter out 4-digit year ranges like 2020-2030
    valid_nums = [
        float(m) for m in matches if not (2020 <= float(m) <= 2030)
    ]

    return valid_nums[0] if valid_nums else 0.0


def extract_bosta_data(pdf_file):
    rows = []

    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                raw_text = page.extract_text() or ""
                full_text = clean_bidi_text(raw_text)

                # 1. Extract Order Reference Name
                name_match = re.search(r"trimize:#(\d+)", full_text)
                name = name_match.group(1) if name_match else ""

                # 2. Extract Shipment ID / Tracking Number
                shipment_id_match = re.search(
                    r"Tracking Number\s*(\d+)", full_text
                )
                if not shipment_id_match:
                    shipment_id_match = re.search(
                        r"(\d{8,11})\s*\n?\s*Order Reference:", full_text
                    )
                if not shipment_id_match:
                    shipment_id_match = re.search(
                        r"\b(\d{9,10})\b", full_text
                    )
                shipment_id = (
                    shipment_id_match.group(1) if shipment_id_match else ""
                )

                # 3. Extract COD using Table Cell Extraction
                total = 0.0
                tables = page.extract_tables()

                # Search through extracted table cells for 'التحصيل' or 'مبلغ'
                cod_found = False
                for table in tables:
                    for row in table:
                        for cell in row:
                            if cell and any(
                                kw in cell
                                for kw in ["التحصيل", "مبلغ", "Cash", "COD"]
                            ):
                                total = parse_cod_from_text(cell)
                                cod_found = True
                                break
                        if cod_found:
                            break
                    if cod_found:
                        break

                # Fallback if table structure wasn't detected on the page
                if not cod_found:
                    total = parse_cod_from_text(full_text)

                financial_status = "Pending" if total > 0 else "Paid"

                # 4. Extract Lineitem SKU & Quantity
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
