# Queue Names
QUEUE_DEFAULT = "default"
QUEUE_LONG = "long"
QUEUE_SHORT = "short"

# Statuses
STATUS_DRAFT = "Draft"
STATUS_SCHEDULED = "Scheduled"
STATUS_SENT = "Sent"
STATUS_FAILED = "Failed"
STATUS_CANCELLED = "Cancelled"
STATUS_QUEUED = "Queued"
STATUS_RUNNING = "Running"
STATUS_COMPLETED = "Completed"
STATUS_PAUSED = "Paused"

# Recipient Statuses
REC_STATUS_PENDING = "Pending"
REC_STATUS_QUEUED = "Queued"
REC_STATUS_PROCESSING = "Processing"
REC_STATUS_SENT = "Sent"
REC_STATUS_DELIVERED = "Delivered"
REC_STATUS_READ = "Read"
REC_STATUS_FAILED = "Failed"

# Dispatch Attempt Statuses
ATTEMPT_STATUS_QUEUED = "Queued"
ATTEMPT_STATUS_SENT = "Sent"
ATTEMPT_STATUS_FAILED = "Failed"


_CAMPAIGN_TERMINAL = {STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED, STATUS_SENT}
_CAMPAIGN_ACTIVE = {STATUS_SCHEDULED, STATUS_QUEUED, STATUS_RUNNING}
_RECIPIENT_TERMINAL = {REC_STATUS_SENT, REC_STATUS_DELIVERED, REC_STATUS_READ, REC_STATUS_FAILED}


def is_terminal_status(status, entity="campaign"):
	if not status:
		return False
	if entity == "campaign":
		return status in _CAMPAIGN_TERMINAL
	if entity == "recipient":
		return status in _RECIPIENT_TERMINAL
	return status in _CAMPAIGN_TERMINAL


def is_active_status(status, entity="campaign"):
	if not status:
		return False
	if entity == "campaign":
		return status in _CAMPAIGN_ACTIVE
	return False


def is_retryable_status(status, entity="recipient"):
	if not status:
		return False
	if entity == "recipient":
		return status == REC_STATUS_FAILED
	return False
