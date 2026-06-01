import frappe
from tap_buddy.services.glific_client import GlificClient

def test():
    frappe.init(site="tapbuddy.local")
    frappe.connect()
    client = GlificClient()
    
    mutation = """
    mutation createSessionTemplate($input: SessionTemplateInput!) {
        createSessionTemplate(input: $input) {
            sessionTemplate { id shortcode status }
            errors { key message }
        }
    }
    """
    
    # Test 1: Realistic Marketing Template (No variables)
    variables1 = {
        "input": {
            "label": "Marketing No Var 1",
            "shortcode": "marketing_novar_1",
            "body": "Special discount on all items! Buy now.",
            "languageId": "1",
            "type": "TEXT",
            "category": "MARKETING",
            "isHsm": True,
            "example": '[]'
        }
    }
    
    # Test 2: Realistic Marketing Template (With variables)
    variables2 = {
        "input": {
            "label": "Marketing Var 1",
            "shortcode": "marketing_var_1",
            "body": "Hi {{1}}, special discount on all items! Buy now.",
            "languageId": "1",
            "type": "TEXT",
            "category": "MARKETING",
            "isHsm": True,
            "example": '["John"]'
        }
    }

    try:
        res1 = client._graphql_request(mutation, variables1)
        print("Test 1 Result:", res1)
    except Exception as e:
        print("Test 1 Exception:", e)
        
    try:
        res2 = client._graphql_request(mutation, variables2)
        print("Test 2 Result:", res2)
    except Exception as e:
        print("Test 2 Exception:", e)

if __name__ == "__main__":
    test()
