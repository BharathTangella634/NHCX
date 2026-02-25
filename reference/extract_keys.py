import json
import sys

def get_paths(obj, current_path, paths_set):
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_path = f"{current_path}.{k}" if current_path else k
            paths_set.add(new_path)
            get_paths(v, new_path, paths_set)
    elif isinstance(obj, list):
        for item in obj:
            get_paths(item, f"{current_path}[]", paths_set)

def extract_keys_from_file(filepath):
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        paths = set()
        get_paths(data, "", paths)
        return sorted(list(paths))
    except Exception as e:
        return [f"Error: {e}"]

if __name__ == "__main__":
    files = [
        "Bundle-DiagnosticReport-Lab-example-03.json",
        "Bundle-DischargeSummary-example-04.json"
    ]
    
    all_keys = set()
    for file in files:
        print(f"--- Keys in {file} ---")
        keys = extract_keys_from_file(file)
        for key in keys:
            print(key)
            all_keys.add(key)
        print("\n")
        
    print("--- All unique keys across both files ---")
    for key in sorted(list(all_keys)):
        if not key.startswith("Error:"):
            print(key)
