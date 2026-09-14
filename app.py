import re
import pandas as pd
import pdfplumber

def extract_bosta_data(pdf_file):
    rows = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            # 1. Extract Name (Order Reference number e.g. 120107)
            name_match = re.search(r'Order Reference:\s*trimize:#(\d+)', text)
            name = name_match.group(1) if name_match else ""

            # 2. Extract Shipment ID 
            # In Bosta tags, the 9-10 digit Shipment ID appears directly before "Order Reference:"
            shipment_id_match = re.search(r'(\d{9,10})\s*\n?\s*Order Reference:', text)
            
            # Fallback search if the layout order shifts slightly
            if not shipment_id_match:
                shipment_id_match = re.search(r'Customer Notes:.*?\n\s*(\d{9,10})', text, re.DOTALL)
                
            shipment_id = shipment_id_match.group(1) if shipment_id_match else ""

            # 3. Extract Financial Status & Total
            # Look for numbers (including decimals like 899.1 or 1,549) anywhere near COD text
            # If a numeric amount exists, it's Pending. If it contains "لا يوجد" or no numbers, it's Paid.
            cod_section = ""
            for line in text.split('\n'):
                if "مبلغ" in line or "التحصيل" in line or "ج.م" in line:
                    cod_section += " " + line

            # Extract numbers/decimals, stripping commas (handles 1,549 or 899.1)
            numbers = re.findall(r'(\d+(?:[\.,]\d+)?)', cod_section)
            
            # Clean commas out of numbers
            clean_numbers = [n.replace(',', '') for n in numbers]

            if clean_numbers and "لا يوجد" not in cod_section:
                financial_status = "Pending"
                total = float(clean_numbers[0])
            else:
                financial_status = "Paid"
                total = 0.0

            # 4. Extract Lineitem SKU and Quantity
            skus_found = re.findall(r'x\s*(\d+)\s*\(?([A-Z0-9\-]+)\)?', text)

            if skus_found:
                for qty, sku in skus_found:
                    rows.append({
                        "Name": name,
                        "Financial Status": financial_status,
                        "Total": total,
                        "Lineitem sku": sku,
                        "Lineitem quantity": int(qty),
                        "Shipment ID": shipment_id
                    })
            else:
                rows.append({
                    "Name": name,
                    "Financial Status": financial_status,
                    "Total": total,
                    "Lineitem sku": "",
                    "Lineitem quantity": 1,
                    "Shipment ID": shipment_id
                })

    return pd.DataFrame(rows)
