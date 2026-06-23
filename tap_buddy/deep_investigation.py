import frappe
import json
from tap_buddy.services.glific_client import GlificClient

def run():
    client = GlificClient()

    print("\n========================================")
    print("PHASE 4 - VERIFY COLLECTION (GROUP) 20996")
    print("========================================")
    query_group = """
    query {
      group(id: 20996) {
        group {
          id
          label
          contactsCount
          waGroupsCount
          waGroups {
            id
            label
          }
        }
      }
    }
    """
    try:
        res = client._graphql_request(query_group, {})
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"Error fetching group 20996: {e}")

    print("\n========================================")
    print("PHASE 5 - TEST waManagedPhoneId = 41")
    print("========================================")
    try:
        query_mutation = """
        mutation sendMessageInWaGroup($input: WaMessageInput!) {
          sendMessageInWaGroup(input: $input) {
            errors {
              key
              message
            }
          }
        }
        """
        variables = {
            "input": {
                "waGroupId": "12125",
                "message": "DIRECT GLIFIC TEST WITH PHONE ID",
                "type": "TEXT",
                "waManagedPhoneId": "41"
            }
        }
        res_mut = client._graphql_request(query_mutation, variables)
        print(json.dumps(res_mut, indent=2))
    except Exception as e:
        print(f"Error testing with waManagedPhoneId: {e}")


