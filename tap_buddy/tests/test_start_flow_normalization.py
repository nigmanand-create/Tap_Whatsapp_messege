import unittest
from unittest.mock import patch
from tap_buddy.services.glific_client import GlificClient

class TestStartContactFlowNormalization(unittest.TestCase):
    @patch('tap_buddy.services.glific_client.GlificClient.get_contact')
    @patch('tap_buddy.services.glific_client._extract_contact_id')
    @patch('tap_buddy.services.glific_client.GlificClient._graphql_request')
    def test_start_contact_flow_normalization(self, mock_graphql, mock_extract, mock_get_contact):
        client = GlificClient()
        mock_extract.return_value = "12345"
        mock_graphql.return_value = {"success": True, "errors": None} # startContactFlow is nested in the query actually, but we just mock the return value of _graphql_request as if it has get("startContactFlow")

        # Mock _graphql_request return value
        mock_graphql.return_value = {"startContactFlow": {"success": True, "errors": None}}

        # Test with +91
        client.start_contact_flow("+918595701049", "40067")
        mock_get_contact.assert_called_with("918595701049")
        
        # Test without +91
        client.start_contact_flow("918595701049", "40067")
        mock_get_contact.assert_called_with("918595701049")

def run():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestStartContactFlowNormalization)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise Exception("Test failed")
