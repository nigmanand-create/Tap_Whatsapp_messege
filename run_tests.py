import sys
import os
import frappe
from pytest import main as pytest_main

print("Initializing Frappe...")
frappe.init(site="tapbuddy.local", sites_path="/Users/blackstar/dev/client/tap-bench/sites")
frappe.connect()
print("Frappe connected. Running Pytest...")

sys.exit(pytest_main(["apps/tap_buddy/tap_buddy", "-v"]))
