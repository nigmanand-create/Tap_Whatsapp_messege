import types

from tap_buddy.services.lms_ingestion import poll_lms_students


def _make_settings():
    s = types.SimpleNamespace()
    s.polling_enabled = True
    s.lms_base_url = "https://lms.evalix.xyz"
    s.lms_api_key = "a2fbaaf31ddfb56:caac2943213af00"
    s.last_polled_at = None
    s.save = lambda ignore_permissions=True: None
    return s


def test_poll_lms_students_enqueues(monkeypatch):
    # Provide fake settings via frappe.get_single
    monkeypatch.setattr("frappe.get_single", lambda name: _make_settings())

    # Fake LMSClient to return two student records
    records = [{"name": "S1", "phone": "+91111"}, {"name": "S2", "phone": "+92222"}]

    class FakeClient:
        def get_students(self, fields=None, limit_page_length=20, filters=None):
            return {"data": records}

    monkeypatch.setattr("tap_buddy.services.lms_ingestion.LMSClient", lambda: FakeClient())

    enqueued = []

    def fake_enqueue(payload, raw_body=None, signature=None, source=None):
        enqueued.append(payload)
        return ["ok"]

    monkeypatch.setattr("tap_buddy.services.lms_ingestion.enqueue_lms_events", fake_enqueue)

    res = poll_lms_students(limit=20)

    assert res.get("status") == "ok"
    assert res.get("processed") == 2
    assert len(enqueued) == 2
