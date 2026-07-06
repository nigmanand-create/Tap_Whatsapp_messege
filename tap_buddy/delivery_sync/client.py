# -*- coding: utf-8 -*-
"""
Glific GraphQL API Client for Delivery Status Synchronization Service.
Executes GraphQL queries and subscription negotiations with resilient retry wrapper.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import requests
import frappe

from tap_buddy.delivery_sync.models import DeliveryStatusEvent
from tap_buddy.delivery_sync.retry import execute_with_retry


class GlificSyncClient:
    """HTTP & GraphQL Client for fetching WhatsApp message delivery statuses from Glific."""

    def __init__(self, endpoint_url: Optional[str] = None, auth_token: Optional[str] = None):
        self.endpoint_url = endpoint_url or frappe.conf.get("glific_graphql_endpoint", "http://localhost:4000/graphql")
        self.auth_token = auth_token or frappe.conf.get("glific_api_token", "")
        self.session = requests.Session()
        if self.auth_token:
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        self.session.headers.update({"Content-Type": "application/json"})

    def fetch_recent_status_updates(
        self,
        since: datetime,
        limit: int = 500,
        offset: int = 0
    ) -> List[DeliveryStatusEvent]:
        """Fetch recently updated WhatsApp messages via GraphQL polling query."""
        query = """
        query FetchMessages($filter: MessageFilter!, $opts: Opts!) {
          messages(filter: $filter, opts: $opts) {
            id
            bspMessageId
            bspStatus
            status
            insertedAt
            updatedAt
            errors
            contact {
              phone
            }
          }
        }
        """
        variables = {
            "filter": {
                "dateRange": {
                    "from": since.isoformat(),
                    "to": datetime.utcnow().isoformat(),
                    "column": "updated_at"
                }
            },
            "opts": {
                "limit": limit,
                "offset": offset,
                "order": "ASC"
            }
        }

        def _do_query():
            resp = self.session.post(self.endpoint_url, json={"query": query, "variables": variables}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if "errors" in data and data["errors"]:
                raise RuntimeError(f"GraphQL Query Errors: {data['errors']}")
            return data.get("data", {}).get("messages", [])

        try:
            raw_messages = execute_with_retry(_do_query, max_retries=3, base_delay=1.0)
            events = []
            for msg in raw_messages:
                bsp_id = msg.get("bspMessageId") or msg.get("bspId")
                if not bsp_id:
                    continue
                events.append(DeliveryStatusEvent.from_glific_graphql(msg))
            return events
        except Exception as e:
            frappe.logger("tap_buddy_delivery_sync").error(f"[FETCH STATUS UPDATES ERROR] {e}")
            raise
