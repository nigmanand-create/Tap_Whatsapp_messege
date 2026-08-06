import frappe
import json
from typing import Dict, Any
from tap_buddy.dynamic_context.builder import ContextBuilder


class CampaignContextBuilder:
    """
    Responsibility:
    - Load campaign metadata
    - Load Dynamic Context
    - Load BigQuery analytics
    - Merge everything
    - Return final context
    """
    def __init__(self, context_builder=None):
        self.context_builder = context_builder or ContextBuilder()
        
    def build_context(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        # 1. Load Dynamic Context & BigQuery (via standard builder)
        context = self.context_builder.build_context(raw_payload)
        
        # 2. Extract Campaign Metadata
        # Webhook payload may place campaign at root or within parameters
        campaign_name = raw_payload.get("campaign")
        if not campaign_name and isinstance(raw_payload.get("parameters"), dict):
            campaign_name = raw_payload["parameters"].get("campaign")
            
        if campaign_name:
            campaign_id = frappe.db.get_value("TAP Campaign", {"campaign_name": campaign_name}, "name")
            if not campaign_id:
                # Fallback to checking by primary key just in case
                if frappe.db.exists("TAP Campaign", campaign_name):
                    campaign_id = campaign_name
                    
            if campaign_id:
                campaign = frappe.get_doc("TAP Campaign", campaign_id)
                
                # Merge custom parameters from the Campaign
                if campaign.flow_custom_parameters:
                    try:
                        custom_params = json.loads(campaign.flow_custom_parameters)
                        if isinstance(custom_params, dict):
                            context.update(custom_params)
                    except Exception as e:
                        frappe.logger("dynamic_context").warning(f"Failed to parse flow_custom_parameters for campaign {campaign_name}: {e}")
                
                # Merge explicitly structured fields
                structured_fields = ["pi_name", "pi_phone", "video_link", "teacher_playbook_link", "registration_portal_link", "registration_deadline"]
                for field in structured_fields:
                    val = campaign.get(field)
                    if val:
                        context[field] = val

        return context
