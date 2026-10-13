import frappe


def resolve_whatsapp_group(label: str) -> str | None:
	if not label:
		return None
	label = str(label).strip()
	if not label:
		return None

	exact = frappe.db.get_value("WhatsApp Group", {"group_name": label}, "name")
	if exact:
		return exact

	by_id = frappe.db.get_value("WhatsApp Group", {"glific_group_id": label}, "name")
	if by_id:
		return by_id

	rows = frappe.get_all(
		"WhatsApp Group",
		filters={"group_name": ["like", f"%{label}%"]},
		fields=["name"],
		limit=1,
	)
	return rows[0].name if rows else None


def resolve_glific_flow(flow_ref: str) -> str | None:
	if not flow_ref:
		return None
	flow_ref = str(flow_ref).strip()
	if not flow_ref:
		return None

	by_id = frappe.db.get_value("Glific Flow", {"flow_id": flow_ref}, "name")
	if by_id:
		return by_id

	by_name = frappe.db.get_value("Glific Flow", {"flow_name": flow_ref}, "name")
	if by_name:
		return by_name

	rows = frappe.get_all(
		"Glific Flow",
		filters={"flow_name": ["like", f"%{flow_ref}%"]},
		fields=["name"],
		limit=1,
	)
	return rows[0].name if rows else None
