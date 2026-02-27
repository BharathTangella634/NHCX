import json
import csv


def convert_fhir_json_to_csv(json_file_path, csv_file_path):
    # Load the JSON data
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # FHIR definitions usually store elements in 'differential' or 'snapshot'
    elements = []
    if 'differential' in data and 'element' in data['differential']:
        elements = data['differential']['element']
    elif 'snapshot' in data and 'element' in data['snapshot']:
        elements = data['snapshot']['element']
    else:
        print("No elements found in the JSON structure.")
        return

    # Define the CSV headers
    headers = ["Element/Key", "Min", "Max", "Type", "Description / Fixed Value"]
    csv_data = []

    # Parse each element in the JSON
    for el in elements:
        key = el.get("id", "")
        min_val = str(el.get("min", ""))
        max_val = str(el.get("max", ""))

        # 1. Extract Data Type and resolve Reference profiles if they exist
        el_type = ""
        if "type" in el and len(el["type"]) > 0:
            types = []
            for t in el["type"]:
                code = t.get("code", "")
                # If it's a reference, grab the specific resources it points to
                if "targetProfile" in t:
                    profiles = [p.split('/')[-1] for p in t["targetProfile"]]
                    code += f"({', '.join(profiles)})"
                types.append(code)
            el_type = " | ".join(types)

        # 2. Extract Description or Fixed Value
        desc = el.get("short", el.get("sliceName", ""))  # Fallback to sliceName if no short desc

        # Look for fixed values (e.g., fixedUri, fixedCode, fixedString)
        fixed_val = ""
        for k, v in el.items():
            if k.startswith("fixed"):
                fixed_val = f"Fixed: {v}"
                break
            elif k.startswith("pattern"):
                fixed_val = f"Pattern: {v}"
                break

        # Prioritize fixed values in the description column
        if fixed_val:
            desc = fixed_val

        # Append row
        csv_data.append([key, min_val, max_val, el_type, desc])

    # Write to the CSV file
    with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(csv_data)

    print(f"Successfully converted '{json_file_path}' to '{csv_file_path}'")


# --- Execution ---
# Make sure your JSON file is in the same directory as this script
# input_json = 'StructureDefinition-DischargeSummaryRecord.json'
# output_csv = 'DischargeSummaryRecord_Keys.csv'

# convert_fhir_json_to_csv(input_json, output_csv)