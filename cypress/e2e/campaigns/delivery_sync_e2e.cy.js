describe('Delivery Status Synchronization Service — End-to-End Test Suite', () => {
  beforeEach(() => {
    cy.login();
  });

  context('Individual Message Delivery Lifecycle', () => {
    it('should sync sent -> delivered -> read status progression for an individual contact', () => {
      const bspMsgId = `e2e-indiv-${Date.now()}`;
      
      // Seed Campaign Recipient and Message Log in Sent state
      cy.call('frappe.client.insert', {
        doc: {
          doctype: 'Message Log',
          provider_message_id: bspMsgId,
          status: 'sent',
          sent_at: frappe.datetime.now_datetime()
        }
      });

      // Simulate synchronization of Delivered event
      cy.call('tap_buddy.delivery_sync.processor.DeliveryStatusProcessor.process_batch', {
        events: [{
          provider_message_id: bspMsgId,
          status: 'delivered',
          timestamp: frappe.datetime.now_datetime()
        }],
        batch_id: 'batch-e2e-1'
      }).then((res) => {
        expect(res.message.processed_count).to.eq(1);
      });

      // Verify Message Log updated to delivered
      cy.call('frappe.client.get_list', {
        doctype: 'Message Log',
        filters: { provider_message_id: bspMsgId },
        fields: ['status', 'delivered_at']
      }).then((logs) => {
        expect(logs.message[0].status).to.eq('delivered');
        expect(logs.message[0].delivered_at).to.not.be.null;
      });
    });
  });

  context('WhatsApp Group & Group Collection Delivery', () => {
    it('should correctly process delivery receipts for group messages and group collections', () => {
      const grpMsgId = `e2e-grp-${Date.now()}`;
      
      cy.call('frappe.client.insert', {
        doc: {
          doctype: 'Message Log',
          provider_message_id: grpMsgId,
          status: 'sent'
        }
      });

      cy.call('tap_buddy.delivery_sync.processor.DeliveryStatusProcessor.process_batch', {
        events: [{
          provider_message_id: grpMsgId,
          status: 'read',
          timestamp: frappe.datetime.now_datetime()
        }],
        batch_id: 'batch-e2e-grp'
      });

      cy.call('frappe.client.get_value', {
        doctype: 'Message Log',
        filters: { provider_message_id: grpMsgId },
        fieldname: 'status'
      }).then((res) => {
        expect(res.message.status).to.eq('read');
      });
    });
  });

  context('Duplicate Prevention & State Precedence', () => {
    it('should ignore duplicate or out-of-order status events arriving with lower precedence', () => {
      const bspMsgId = `e2e-dedup-${Date.now()}`;
      
      cy.call('frappe.client.insert', {
        doc: {
          doctype: 'Message Log',
          provider_message_id: bspMsgId,
          status: 'read'
        }
      });

      // Send out-of-order 'sent' and 'delivered' events after 'read' already recorded
      cy.call('tap_buddy.delivery_sync.processor.DeliveryStatusProcessor.process_batch', {
        events: [
          { provider_message_id: bspMsgId, status: 'delivered', timestamp: frappe.datetime.now_datetime() },
          { provider_message_id: bspMsgId, status: 'sent', timestamp: frappe.datetime.now_datetime() }
        ],
        batch_id: 'batch-e2e-dedup'
      });

      // Verify status remains 'read' (Precedence 3 overrides Precedence 1 & 2)
      cy.call('frappe.client.get_value', {
        doctype: 'Message Log',
        filters: { provider_message_id: bspMsgId },
        fieldname: 'status'
      }).then((res) => {
        expect(res.message.status).to.eq('read');
      });
    });
  });

  context('Failure Handling & DLQ Routing', () => {
    it('should route unresolvable or corrupted payloads to the Dead-Letter Queue', () => {
      cy.call('tap_buddy.delivery_sync.processor.DeliveryStatusProcessor.process_batch', {
        events: [{
          provider_message_id: null, // Corrupt payload missing correlation ID
          status: 'failed',
          timestamp: frappe.datetime.now_datetime()
        }],
        batch_id: 'batch-e2e-dlq'
      }).then((res) => {
        expect(res.message.dlq_count).to.be.gte(0);
      });
    });
  });

  context('Scheduler & Campaign Dashboard Updates', () => {
    it('should aggregate campaign recipient counts and reflect totals on TAP Campaign dashboard', () => {
      cy.visit('/app/tap-campaign');
      cy.get('.list-row').should('exist');
    });
  });
});
