import json
import sys
import re

def is_uuid(value):
    if not isinstance(value, str):
        return False
    # Handle "urn:uuid:xxxxx"
    val = value.replace('urn:uuid:', '')
    pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
    return bool(re.match(pattern, val))

def get_date_format(value):
    if not isinstance(value, str):
        return None
    
    # FHIR Datetimes can be: 2020-09-29T14:58:58.181+05:30
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{2}:\d{2}$', value):
        return "<DATE_FORMAT: YYYY-MM-DDThh:mm:ss.sss+zz:zz>"
    # 2020-09-29T14:58:58+05:30
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$', value):
        return "<DATE_FORMAT: YYYY-MM-DDThh:mm:ss+zz:zz>"
    # 2020-09-29T14:58:58Z
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', value):
        return "<DATE_FORMAT: YYYY-MM-DDThh:mm:ssZ>"
    # 2020-09-29
    if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
        return "<DATE_FORMAT: YYYY-MM-DD>"
    # 2020-09
    if re.match(r'^\d{4}-\d{2}$', value):
        return "<DATE_FORMAT: YYYY-MM>"
    # 2020 (Year only, ensure valid range to avoid false positives on numbers)
    if re.match(r'^\d{4}$', value) and 1900 <= int(value) <= 2100:
        return "<DATE_FORMAT: YYYY>"
    
    return None

def extract_structure(data, key_name=None):
    """Recursively extract the hierarchical structure of keys with special value rules."""
    if isinstance(data, dict):
        structure = {}
        for key, value in data.items():
            structure[key] = extract_structure(value, key)
        return structure
    elif isinstance(data, list):
        if not data:
            return []
        
        # Merge structures from all elements in the list to get a comprehensive map
        merged_structure = {}
        has_dict = False
        
        for item in data:
            if isinstance(item, dict):
                has_dict = True
                item_struct = extract_structure(item, key_name)
                for k, v in item_struct.items():
                    if k not in merged_structure:
                        merged_structure[k] = v
                    elif isinstance(v, dict) and isinstance(merged_structure[k], dict):
                        # Simple merge for nested dicts
                        merged_structure[k].update(v)
        
        if has_dict:
            return [merged_structure]
        else:
            # List of simple types (like list of strings for 'profile')
            # Assuming all elements have similar type/format, use the first one
            return [extract_structure(data[0], key_name)]
    else:
        # Rules for literal values based on prompt
        if key_name in ['profile', 'system', 'code', 'language']:
            return data
        
        if is_uuid(data):
            return "<UUID>"
        
        date_format = get_date_format(data)
        if date_format:
            return date_format
            
        return type(data).__name__

def main():
    input_file = "Bundle-DiagnosticReport-Lab-example-03.json"
    output_file = "diagnostic_report_map.json"
    
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
            
        structure = extract_structure(data)
        
        with open(output_file, 'w') as f:
            json.dump(structure, f, indent=2)
            
        print(f"Hierarchical map successfully created and saved to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
