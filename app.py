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

            # 2. Extract Shipment ID (9-10 digit tracking number)
            shipment_id_match = re.search(r'(\d{9,10})\s*\n?\s*Order Reference:', text)
            if not shipment_id_match:
                shipment_id_match = re.search(r'Customer Notes:.*?\n\s*(\d{9,10})', text, re.DOTALL)
            shipment_id = shipment_id_match.group(1) if shipment_id_match else ""

            # 3. Robust Financial Status & Total Extraction
            # Bosta lists cash collection values formatted as numbers (e.g., 999, 899.1, 1,500.00)
            # Search for COD values directly by isolating standalone numeric prices on the page
            cod_matches = re.findall(r'(?:COD|Cash|Amount|Total)?\s*[:\.-]?\s*(\d+(?:[\.,]\d+)?)', text, re.IGNORECASE)
            
            # Filter extracted numbers to isolate reasonable COD total amounts 
            # (Excluding Order Reference digits, Shipment IDs, and quantities)
            valid_totals = []
            for num in re.findall(r'\b\d+(?:[\.,]\d+)?\b', text):
                clean_num_str = num.replace(',', '')
                try:
                    val = float(clean_num_str)
                    # Ignore values that match Shipment ID or Order Reference
                    if clean_num_str != shipment_id and clean_num_str != name:
                        # Exclude small item quantities (1-10) unless it's explicitly a total
                        if val > 10 or '.' in num:
                            valid_totals.append(val)
                except ValueError:
                    continue

            if valid_totals:
                # The COD amount is typically the highest standalone price value on the tag
                total = valid_totals[0]
                financial_status = "Pending" if total > 0 else "Paid"
            else:
                total = 0.0
                financial_status = "Paid"

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
