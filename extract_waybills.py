import re
import pandas as pd
import pdfplumber

def parse_bosta_pdf(pdf_path):
    records = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(layout=False) or ""
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # 1. Order Reference
            order_ref = None
            ref_match = re.search(r'Order Reference:\s*(trimize:#\d+|\S+)', text)
            if ref_match:
                order_ref = ref_match.group(1)
            
            # 2. Tracking Number
            tracking_num = None
            track_match = re.search(r'(\b\d{9,10}\b)', text)
            if track_match:
                tracking_num = track_match.group(1)
                
            # 3. Customer Name & Phone
            name, phone = None, None
            for idx, line in enumerate(lines):
                if "توصيل إلى:" in line and idx + 2 < len(lines):
                    name = lines[idx + 1]
                    phone_match = re.search(r'(\+?\d{11,13})', lines[idx + 2])
                    if phone_match:
                        phone = phone_match.group(1)
                    break

            # 4. Collection Amount (COD)
            cod_amount = "0"
            cod_match = re.search(r'مبلغ التحصيل:\s*([^\n|]+)', text)
            if cod_match:
                raw_cod = cod_match.group(1).strip()
                if "لا يوجد" in raw_cod:
                    cod_amount = "0.00"
                else:
                    # Clean out currency symbols and unexpected LaTeX characters (e.g. page 17 issue)
                    cleaned_cod = re.sub(r'[^\d.]', '', raw_cod)
                    cod_amount = cleaned_cod if cleaned_cod else "0.00"

            # 5. Item Description / Bundle
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

# Run extraction
df = parse_bosta_pdf("airwaybill_2.pdf")

# Export to Excel
df.to_excel("parsed_airway_bills.xlsx", index=False)
print("Extraction complete. Output saved to parsed_airway_bills.xlsx")
