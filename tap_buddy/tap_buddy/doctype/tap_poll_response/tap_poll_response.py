from frappe.model.document import Document


class TAPPollResponse(Document):
    """Frappe Document controller for immutable TAP Poll Response records.

    Poll response records are written once by the webhook handler and are
    never mutated afterwards.  The controller intentionally carries no
    business logic — all validation and insertion is performed by the
    dedicated API endpoint (tap_buddy.api.poll_response).
    """
    pass
