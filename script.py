import frappe
from frappe.utils import now_datetime
from tap_buddy.services.webhook_processor import enqueue_webhook_events, process_webhook_event

frappe.set_user('Administrator')
school = frappe.get_doc({'doctype':'School','school_name':'Webhook Test School','whatsapp_number':'+911234567890'}).insert(ignore_permissions=True)
campaign = frappe.get_doc({'doctype':'TAP Campaign','campaign_name':'Webhook Test Campaign','status':'Scheduled','send_date':now_datetime()}).insert(ignore_permissions=True)
recipient = frappe.get_doc({'doctype':'Campaign Recipient','campaign':campaign.name,'school':school.name,'status':'Sent','sent_time':now_datetime()}).insert(ignore_permissions=True)
log = frappe.get_doc({'doctype':'Message Log','campaign':campaign.name,'school':school.name,'phone_number':'+911234567890','message':'hi','status':'Sent','provider_message_id':'whk-test-1','sent_at':now_datetime()}).insert(ignore_permissions=True)

names = enqueue_webhook_events({'provider_message_id':'whk-test-1','status':'delivered'})
process_webhook_event(names[0])

updated_log = frappe.get_doc('Message Log', log.name)
updated_recipient = frappe.get_doc('Campaign Recipient', recipient.name)
print(updated_log.status, updated_recipient.status)
