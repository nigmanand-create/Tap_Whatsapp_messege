import frappe
import unittest
from unittest.mock import patch, MagicMock
from tap_buddy.tasks.scheduler import _dispatch_flow_campaign

class TestGroupCollectionDispatch(unittest.TestCase):
    def setUp(self):
        self.campaign = MagicMock()
        self.campaign.name = "CAMP-01"
        self.campaign.glific_flow = "FLOW-01"
        
        self.recipient = MagicMock()
        self.recipient.name = "REC-01"
        self.recipient.whatsapp_group = "WAG-01"
        
        self.client = MagicMock()
        self.group_doc = MagicMock()
        self.group_doc.name = "WAG-01"

    @patch("tap_buddy.tasks.scheduler._mark_failed")
    @patch("frappe.get_doc")
    @patch("frappe.get_all")
    def test_missing_mapping(self, mock_get_all, mock_get_doc, mock_mark_failed):
        mock_get_doc.return_value = self.group_doc
        mock_get_all.return_value = [] # No mappings
        
        _dispatch_flow_campaign(self.client, self.campaign, self.recipient)
        self.client.start_group_flow.assert_not_called()
        mock_mark_failed.assert_called_once()
        self.assertIn("Missing Mapping", mock_mark_failed.call_args[0][1])

    @patch("tap_buddy.tasks.scheduler.now_datetime")
    @patch("frappe.db.set_value")
    @patch("tap_buddy.tasks.scheduler._update_dispatch_attempt_success")
    @patch("tap_buddy.tasks.scheduler._create_dispatch_attempt")
    @patch("frappe.get_doc")
    @patch("frappe.get_all")
    def test_valid_mapping(self, mock_get_all, mock_get_doc, mock_create, mock_success, mock_set_value, mock_now):
        mock_now.return_value = "2026-01-01 00:00:00"
        mock_get_doc.return_value = self.group_doc
        mock_get_all.return_value = [{"collection": "COL-01", "glific_collection_id": "777"}]
        
        _dispatch_flow_campaign(self.client, self.campaign, self.recipient)
        self.client.start_group_flow.assert_called_once_with("777", "FLOW-01")

    @patch("tap_buddy.tasks.scheduler._mark_failed")
    @patch("frappe.get_doc")
    @patch("frappe.get_all")
    def test_broken_collection(self, mock_get_all, mock_get_doc, mock_mark_failed):
        mock_get_doc.return_value = self.group_doc
        mock_get_all.return_value = [{"collection": "COL-01", "glific_collection_id": None}]
        
        _dispatch_flow_campaign(self.client, self.campaign, self.recipient)
        self.client.start_group_flow.assert_not_called()
        mock_mark_failed.assert_called_once()
        self.assertIn("Invalid Collection ID", mock_mark_failed.call_args[0][1])

    @patch("tap_buddy.tasks.scheduler.now_datetime")
    @patch("frappe.db.set_value")
    @patch("tap_buddy.tasks.scheduler._update_dispatch_attempt_success")
    @patch("tap_buddy.tasks.scheduler._create_dispatch_attempt")
    @patch("frappe.get_doc")
    @patch("frappe.get_all")
    def test_multiple_mappings(self, mock_get_all, mock_get_doc, mock_create, mock_success, mock_set_value, mock_now):
        mock_now.return_value = "2026-01-01 00:00:00"
        mock_get_doc.return_value = self.group_doc
        mock_get_all.return_value = [
            {"collection": "COL-01", "glific_collection_id": "777"},
            {"collection": "COL-02", "glific_collection_id": "888"}
        ]
        
        _dispatch_flow_campaign(self.client, self.campaign, self.recipient)
        args = self.client.start_group_flow.call_args[0]
        self.assertEqual(args[0], "777") # Selects the first one
        self.assertEqual(args[1], "FLOW-01")


