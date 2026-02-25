from fhir.resources.bundle import Bundle

def tabulate_bundle_entries(bundle: Bundle):
    print(f"{'idx':>3}  {'resourceType':15}  {'id':20}  {'lastUpdated'}")
    print("-" * 60)
    for i, e in enumerate(bundle.entry or []):
        r = e.resource
        if r is None:
            print(f"{i:>3}  {'(no resource)':15}  {'':20}  ")
            continue
        rid = getattr(r, "id", "") or ""
        last_updated = ""
        if getattr(r, "meta", None) is not None:
            last_updated = str(getattr(r.meta, "lastUpdated", "") or "")
        print(f"{i:>3}  {r.get_resource_type():15}  {rid:20}  {last_updated}")

# Example:
# b = Bundle.model_validate_json(bundle_json_bytes)
# tabulate_bundle_entries(b)
