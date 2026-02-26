import json

file_path = "reference/diagnostic_report/Bundle-DiagnosticReport-Lab-example-03.json"
with open(file_path, "r") as f:
    content = json.load(f)

def replace_data(node):
    if isinstance(node, dict):
        for k, v in list(node.items()):
            if k == "data" and isinstance(v, str) and len(v) > 100:
                if v.startswith("JVBERi"):
                    node[k] = "<DATA>"
                else:
                    node[k] = "<ENCRYPTED_DATA>"
            else:
                replace_data(v)
    elif isinstance(node, list):
        for item in node:
            replace_data(item)

replace_data(content)

with open(file_path, "w") as f:
    json.dump(content, f, indent=2)
