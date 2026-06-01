import frappe
from tap_buddy.services.glific_client import GlificClient

def check_glific_count():
    client = GlificClient()
    query = """
    query sessionTemplates($filter: SessionTemplateFilter) {
        sessionTemplatesCount(filter: $filter) 
    }
    """
    data = client._graphql_request(query, {})
    print("Total Glific Templates:", data.get("sessionTemplatesCount"))

if __name__ == "__main__":
    check_glific_count()
