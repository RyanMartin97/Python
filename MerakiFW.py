"""
Export Layer 3 Firewall Rules from all Meraki MX networks in an organisation.
 
Outputs:
  - meraki_l3_rules.csv   (all rules across all networks)
  - meraki_l3_rules.json  (raw API response, per network)
 
Requirements:
  pip install meraki
"""
 
import csv
import json
import os
import sys
import meraki
 
 
# ---------------------------------------------------------------------------
# Configuration – set via environment variables or edit the defaults below
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("MERAKI_API_KEY", "YOUR_API_KEY_HERE")
ORG_ID  = os.environ.get("MERAKI_ORG_ID", "")   # leave blank to auto-detect
 
OUTPUT_CSV  = "meraki_l3_rules.csv"
OUTPUT_JSON = "meraki_l3_rules.json"
# ---------------------------------------------------------------------------
 
 
def get_org_id(dashboard: meraki.DashboardAPI) -> str:
    """Return the first organisation ID if ORG_ID is not set."""
    orgs = dashboard.organizations.getOrganizations()
    if not orgs:
        sys.exit("No organisations found for this API key.")
    if len(orgs) == 1:
        return orgs[0]["id"]
    print("Multiple organisations found:")
    for i, org in enumerate(orgs):
        print(f"  [{i}] {org['name']}  (id: {org['id']})")
    choice = int(input("Select organisation number: "))
    return orgs[choice]["id"]
 
 
def get_mx_networks(dashboard: meraki.DashboardAPI, org_id: str) -> list[dict]:
    """Return all networks that contain an MX (appliance) device."""
    networks = dashboard.organizations.getOrganizationNetworks(
        org_id, total_pages="all"
    )
    mx_networks = [n for n in networks if "appliance" in n.get("productTypes", [])]
    print(f"Found {len(mx_networks)} MX network(s) in org {org_id}.")
    return mx_networks
 
 
def fetch_l3_rules(dashboard: meraki.DashboardAPI, networks: list[dict]) -> dict:
    """
    Fetch L3 firewall rules for every MX network.
 
    Returns a dict: { network_id: { "name": ..., "rules": [...] } }
    """
    results = {}
    for net in networks:
        net_id   = net["id"]
        net_name = net["name"]
        try:
            rules = dashboard.appliance.getNetworkApplianceFirewallL3FirewallRules(net_id)
            results[net_id] = {"name": net_name, "rules": rules.get("rules", [])}
            print(f"  ✓  {net_name}: {len(results[net_id]['rules'])} rule(s)")
        except meraki.APIError as exc:
            print(f"  ✗  {net_name}: API error – {exc}")
            results[net_id] = {"name": net_name, "rules": [], "error": str(exc)}
    return results
 
 
def write_csv(all_rules: dict, filepath: str) -> None:
    """Flatten rules from all networks into a single CSV file."""
    fieldnames = [
        "network_id", "network_name", "rule_index",
        "comment", "policy", "protocol",
        "srcPort", "srcCidr",
        "destPort", "destCidr",
        "syslogEnabled",
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for net_id, data in all_rules.items():
            for idx, rule in enumerate(data["rules"], start=1):
                writer.writerow({
                    "network_id":   net_id,
                    "network_name": data["name"],
                    "rule_index":   idx,
                    **rule,
                })
    print(f"\nCSV  saved → {filepath}")
 
 
def write_json(all_rules: dict, filepath: str) -> None:
    """Write the raw per-network rule data as JSON."""
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(all_rules, fh, indent=2)
    print(f"JSON saved → {filepath}")
 
 
def main() -> None:
    if API_KEY == "YOUR_API_KEY_HERE":
        sys.exit(
            "Set your Meraki API key via the MERAKI_API_KEY environment variable "
            "or edit API_KEY in the script."
        )
 
    dashboard = meraki.DashboardAPI(
        API_KEY,
        suppress_logging=True,   # set False to see raw HTTP calls
        output_log=False,
    )
 
    org_id = ORG_ID or get_org_id(dashboard)
    print(f"Using organisation ID: {org_id}\n")
 
    mx_networks = get_mx_networks(dashboard, org_id)
    if not mx_networks:
        sys.exit("No MX networks found – nothing to export.")
 
    all_rules = fetch_l3_rules(dashboard, mx_networks)
 
    write_csv(all_rules, OUTPUT_CSV)
    write_json(all_rules, OUTPUT_JSON)
 
    total_rules = sum(len(v["rules"]) for v in all_rules.values())
    print(f"\nDone. {total_rules} rule(s) exported across {len(mx_networks)} network(s).")
 
 
if __name__ == "__main__":
    main()