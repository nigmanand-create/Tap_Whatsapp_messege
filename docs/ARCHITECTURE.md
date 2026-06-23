# Architecture Overview
Please see the specific files in the `architecture/` folder for detailed breakdowns:

- [Domain Model](architecture/domain_model.md)
- [Service Catalog](architecture/service_catalog.md)
- [API Catalog](architecture/api_catalog.md)
- [Integration Catalog](architecture/integration_catalog.md)
- [Database Design](architecture/database_design.md)


## WhatsApp Group vs Glific Collection

**Architectural Distinction:**
1. **WhatsApp Group (`glific_group_id`)**: The native ID of a WhatsApp Group inside Glific. This ID is used strictly for **Standard Group Messaging** (`sendGroupMessage`).
2. **Contact Collection (`glific_collection_id`)**: A Glific feature that groups contacts together. When starting a **Group Flow** (`startGroupFlow`), the Glific API strictly requires the ID of the **Contact Collection** representing the group, *not* the WhatsApp Group ID.

**Mapping Workflow:**
- `WhatsApp Group` records sync down the `glific_group_id`.
- `group_collection_sync.py` creates a `WhatsApp Group Collection Mapping` that links the `WhatsApp Group` to its corresponding `WhatsApp Group Collection`.
- When `_dispatch_flow_campaign` runs, it dynamically resolves the `glific_collection_id` via the `WhatsApp Group Collection Mapping`. If a mapping is missing or broken, the dispatch fails safely.
