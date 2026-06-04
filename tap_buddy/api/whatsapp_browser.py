import frappe

@frappe.whitelist()
def get_collections(search_text=None, limit_start=0, limit_page_length=50):
    conditions = []
    values = {}
    
    if search_text:
        conditions.append("c.collection_name LIKE %(search_text)s")
        values["search_text"] = f"%{search_text}%"
        
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    sql = f"""
        SELECT 
            c.name as collection_id, 
            c.collection_name as name,
            COUNT(m.whatsapp_group) as group_count
        FROM `tabWhatsApp Group Collection` c
        INNER JOIN `tabWhatsApp Group Collection Mapping` m ON m.collection = c.name
        {where_clause}
        GROUP BY c.name
        ORDER BY c.collection_name ASC
        LIMIT {int(limit_page_length)} OFFSET {int(limit_start)}
    """
    
    count_sql = f"""
        SELECT COUNT(DISTINCT c.name) as total
        FROM `tabWhatsApp Group Collection` c
        INNER JOIN `tabWhatsApp Group Collection Mapping` m ON m.collection = c.name
        {where_clause}
    """
    
    results = frappe.db.sql(sql, values, as_dict=True)
    total_res = frappe.db.sql(count_sql, values, as_dict=True)
    total = total_res[0].total if total_res else 0
    
    return {
        "data": results,
        "total": total
    }

@frappe.whitelist()
def get_collection_details(collection_id, search_text=None, limit_start=0, limit_page_length=50):
    conditions = ["m.collection = %(collection_id)s"]
    values = {"collection_id": collection_id}
    
    if search_text:
        conditions.append("g.group_name LIKE %(search_text)s")
        values["search_text"] = f"%{search_text}%"
        
    where_clause = f"WHERE {' AND '.join(conditions)}"
    
    sql = f"""
        SELECT 
            g.name as group_id,
            g.group_name,
            g.participant_count,
            g.last_communication_at
        FROM `tabWhatsApp Group Collection Mapping` m
        INNER JOIN `tabWhatsApp Group` g ON g.name = m.whatsapp_group
        {where_clause}
        ORDER BY g.group_name ASC
        LIMIT {int(limit_page_length)} OFFSET {int(limit_start)}
    """
    
    count_sql = f"""
        SELECT COUNT(g.name) as total
        FROM `tabWhatsApp Group Collection Mapping` m
        INNER JOIN `tabWhatsApp Group` g ON g.name = m.whatsapp_group
        {where_clause}
    """
    
    results = frappe.db.sql(sql, values, as_dict=True)
    total_res = frappe.db.sql(count_sql, values, as_dict=True)
    total = total_res[0].total if total_res else 0
    
    col_name = frappe.db.get_value("WhatsApp Group Collection", collection_id, "collection_name")
    
    return {
        "collection_name": col_name,
        "data": results,
        "total": total
    }

@frappe.whitelist()
def trigger_sync():
    from tap_buddy.services.group_collection_sync import sync_collections_and_groups
    try:
        res = sync_collections_and_groups()
        return res
    except Exception as e:
        frappe.throw(f"Sync failed: {str(e)}")
