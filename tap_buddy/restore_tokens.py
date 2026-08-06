import frappe

def restore():
    settings = frappe.get_single('TAP Buddy Settings')
    settings.db_set('glific_access_token', 'SFMyNTY.YzgxMGRhN2QtNWY0ZS00ZGE2LThmMTktZGRmNTY3OGUxY2Fk.uNh1VmOvV9iLhC_BVTjrpq7kQv7n1dRG3C1rZoke8Ak')
    settings.db_set('glific_refresh_token', 'SFMyNTY.YmU4MWEzN2UtOGUxNy00M2M3LTkzYWItMTlhYmEyNjIxYTJl.WSx5xWZiLfzHZX-ARCWn2oInTFKmlZFmeI5GuusF-uk')
    frappe.db.commit()
    print('Tokens restored')
