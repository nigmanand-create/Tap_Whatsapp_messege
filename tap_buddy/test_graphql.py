import json
import frappe
from tap_buddy.services.glific_client import GlificClient

def fetch_flows():
    client = GlificClient()
    client.ensure_valid_token()
    
    query = '''
    query {
      __type(name: "ExportFlow") {
        fields {
          name
          type { name kind ofType { name kind } }
        }
      }
    }
    '''
    
    try:
        resp = client._graphql_request(query)
        print("RESP:", json.dumps(resp, indent=2))
    except Exception as e:
        print("ERROR:", str(e))

