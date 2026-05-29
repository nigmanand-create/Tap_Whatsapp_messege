import sys
import os
import frappe
from pytest import main as pytest_main

print("Initializing Frappe...")
frappe.init(site="tapbuddy.local", sites_path=".")
frappe.connect()
print("Frappe connected. Running Pytest...")
sys.exit(pytest_main(sys.argv[1:]))
