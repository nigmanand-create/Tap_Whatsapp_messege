# Glific API Data Tracking Guide

This document outlines the key data points you can track from Glific using its APIs, providing answers to metrics like message read receipts, user flow tracking, and contact management.

## 📌 Important Note on Glific APIs
As mentioned in the official documentation, **Glific uses GraphQL for all its APIs**, with the only exception being Authentication (which uses REST). 

This means that for fetching ANY tracking data, you won't use different URLs for different data points. Instead, you will make a `POST` request to a **single GraphQL endpoint**, passing specific queries in the request body (payload) to specify what data you want.

**Base GraphQL Endpoint:**
`POST https://api.YOURSITENAME.glific.com/api/v1/graphql`

*(You must include your Authentication token in the headers as `Authorization: Bearer <TOKEN>` for all requests).*

---

## 1. Message Tracking (Delivery & Read Receipts)
**What you can track:** 
- How many people received a particular message.
- How many people actually **read** a message (Read Receipts).
- Which messages failed to deliver.

**API Link:** `POST https://api.YOURSITENAME.glific.com/api/v1/graphql`

**Payload Structure (GraphQL Query):**
```json
{
  "query": "query { messages(filter: { type: \"hsm\" }) { id body status contact { name phone } insertedAt updatedAt } }"
}
```
*💡 **Insight:** The `status` field in the response will tell you if the message is `sent`, `delivered`, `read`, or `failed`.*

---

## 2. Contact & User Demographics Tracking
**What you can track:**
- Total number of registered contacts.
- Contact phone numbers, names, and whether they have opted-in to receive messages.
- When the contact last interacted with the bot (`lastMessageAt`).

**API Link:** `POST https://api.YOURSITENAME.glific.com/api/v1/graphql`

**Payload Structure (GraphQL Query):**
```json
{
  "query": "query { contacts { id name phone status lastMessageAt optinTime } }"
}
```

---

## 3. Flow Tracking (Chatbot Journeys)
**What you can track:**
- Which conversational flows a user has started or completed.
- Where a user dropped off in a specific flow (abandonment rate).

**API Link:** `POST https://api.YOURSITENAME.glific.com/api/v1/graphql`

**Payload Structure (GraphQL Query):**
```json
{
  "query": "query { flowResults { id contact { phone } flow { name } node status insertedAt } }"
}
```
*💡 **Insight:** Tracking the `node` or `status` helps you identify exactly which question/step in the flow the user is currently on.*

---

## 4. Tags & Segmentation Tracking
**What you can track:**
- How many users fall under a specific tag (e.g., tracking how many people clicked a specific CTA by tagging them).
- Grouping metrics for targeted campaigns.

**API Link:** `POST https://api.YOURSITENAME.glific.com/api/v1/graphql`

**Payload Structure (GraphQL Query):**
```json
{
  "query": "query { tags { id name contactsCount } }"
}
```

---

## 🚀 How to execute these requests (cURL Example)
To test fetching the **Message Read Status**, you can use the following cURL command. Just replace `YOURSITENAME` and `YOUR_ACCESS_TOKEN`.

```bash
curl --location 'https://api.YOURSITENAME.glific.com/api/v1/graphql' \
--header 'Content-Type: application/json' \
--header 'Accept: application/json' \
--header 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
--data '{
    "query": "query { messages(limit: 100) { id status body contact { phone } } }"
}'
```

---
**Developer Note:** Because Glific uses GraphQL, you can fetch Contacts, Messages, and Flow Results all in a single API call if needed. You can use tools like Postman (GraphQL mode) or Altair to introspect your specific Glific workspace and see the exact schema fields available.
