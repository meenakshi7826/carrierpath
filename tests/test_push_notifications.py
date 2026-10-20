import json
import importlib
import io
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pywebpush import WebPushException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app


class PushNotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database = app.DATABASE
        app.DATABASE = Path(self.temp_directory.name) / "test.sqlite3"
        self.private_key = Path(self.temp_directory.name) / "private_key.pem"
        self.private_key.write_text("test key", encoding="utf-8")
        app.initialize_database()

    def tearDown(self):
        app.DATABASE = self.database
        self.temp_directory.cleanup()

    def subscription_payload(
        self,
        reminder_time="20:00",
        timezone_name="Asia/Kolkata",
        endpoint="https://fcm.googleapis.com/fcm/send/test-endpoint",
    ):
        return {
            "subscription": {
                "endpoint": endpoint,
                "keys": {"auth": "auth-key", "p256dh": "public-key"},
                "expirationTime": None,
            },
            "reminder_time": reminder_time,
            "timezone": timezone_name,
        }

    def test_rejects_untrusted_push_endpoint(self):
        payload = self.subscription_payload()
        payload["subscription"]["endpoint"] = "https://127.0.0.1/admin"

        with self.assertRaisesRegex(ValueError, "endpoint is not supported"):
            app.save_push_subscription(payload)

    def test_rejects_invalid_time_zone(self):
        payload = self.subscription_payload(timezone_name="Not/AZone")

        with self.assertRaisesRegex(ValueError, "valid time zone"):
            app.save_push_subscription(payload)

    def test_subscription_updates_existing_browser_schedule(self):
        app.save_push_subscription(self.subscription_payload())
        app.save_push_subscription(self.subscription_payload(reminder_time="21:15"))

        with closing(sqlite3.connect(app.DATABASE)) as connection:
            row = connection.execute(
                "SELECT reminder_time, timezone, enabled FROM push_subscriptions"
            ).fetchone()

        self.assertEqual(row, ("21:15", "Asia/Kolkata", 1))

    def test_sends_due_reminder_once_per_local_day(self):
        app.save_push_subscription(self.subscription_payload())
        send = Mock()
        now = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)

        with patch.dict(
            "os.environ",
            {
                "VAPID_PUBLIC_KEY": "public-key",
                "VAPID_PRIVATE_KEY": str(self.private_key),
                "VAPID_SUBJECT": "mailto:admin@example.com",
            },
        ):
            first_result = app.send_due_reminders(now, push_sender=send)
            second_result = app.send_due_reminders(now, push_sender=send)

        self.assertEqual(first_result["sent"], 1)
        self.assertEqual(second_result["sent"], 0)
        self.assertEqual(send.call_count, 1)
        notification = json.loads(send.call_args.kwargs["data"])
        self.assertEqual(notification["url"], "/#study")
        self.assertEqual(send.call_args.kwargs["headers"], {})
        self.assertEqual(send.call_args.kwargs["ttl"], 3600)

    def test_windows_push_uses_raw_notification_headers(self):
        payload = self.subscription_payload(
            endpoint="https://wns2.notify.windows.com/w/?token=test"
        )
        app.save_push_subscription(payload)
        send = Mock()
        now = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)

        with patch.dict(
            "os.environ",
            {
                "VAPID_PUBLIC_KEY": "public-key",
                "VAPID_PRIVATE_KEY": str(self.private_key),
                "VAPID_SUBJECT": "mailto:admin@example.com",
            },
        ):
            result = app.send_due_reminders(now, push_sender=send)

        self.assertEqual(result["sent"], 1)
        self.assertEqual(
            send.call_args.kwargs["headers"],
            {
                "X-WNS-Type": "wns/raw",
                "Content-Type": "application/octet-stream",
            },
        )
        self.assertEqual(send.call_args.kwargs["ttl"], 600)

    def test_failed_delivery_is_retried_on_next_scheduler_run(self):
        app.save_push_subscription(self.subscription_payload())
        send = Mock(
            side_effect=[
                WebPushException(
                    "Temporary push service failure",
                    response=SimpleNamespace(status_code=503),
                ),
                None,
            ]
        )
        now = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)

        with patch.dict(
            "os.environ",
            {
                "VAPID_PUBLIC_KEY": "public-key",
                "VAPID_PRIVATE_KEY": str(self.private_key),
                "VAPID_SUBJECT": "mailto:admin@example.com",
            },
        ):
            with patch("builtins.print"):
                first_result = app.send_due_reminders(now, push_sender=send)
            second_result = app.send_due_reminders(now, push_sender=send)

        self.assertEqual(first_result["failed"], 1)
        self.assertEqual(second_result["sent"], 1)
        self.assertEqual(send.call_count, 2)

    def test_does_not_send_before_local_reminder_time(self):
        app.save_push_subscription(self.subscription_payload())
        send = Mock()
        now = datetime(2026, 10, 20, 13, 0, tzinfo=timezone.utc)

        with patch.dict(
            "os.environ",
            {
                "VAPID_PUBLIC_KEY": "public-key",
                "VAPID_PRIVATE_KEY": str(self.private_key),
                "VAPID_SUBJECT": "mailto:admin@example.com",
            },
        ):
            result = app.send_due_reminders(now, push_sender=send)

        self.assertEqual(result["sent"], 0)
        send.assert_not_called()

    def test_wsgi_serves_worker_and_push_subscription_endpoints(self):
        import wsgi

        wsgi = importlib.reload(wsgi)

        def request(method, path, payload=None):
            body = json.dumps(payload).encode("utf-8") if payload is not None else b""
            environ = {
                "REQUEST_METHOD": method,
                "PATH_INFO": path,
                "CONTENT_LENGTH": str(len(body)),
                "wsgi.input": io.BytesIO(body),
            }
            captured = {}

            def start_response(status, headers):
                captured["status"] = int(status.split()[0])
                captured["headers"] = dict(headers)

            response_body = b"".join(wsgi.application(environ, start_response))
            return captured, response_body

        worker_response, worker_body = request("GET", "/service-worker.js")
        self.assertEqual(worker_response["status"], 200)
        self.assertIn(b"showNotification", worker_body)

        payload = self.subscription_payload()
        save_response, _ = request("POST", "/api/push/subscriptions", payload)
        self.assertEqual(save_response["status"], 201)

        delete_response, delete_body = request(
            "DELETE",
            "/api/push/subscriptions",
            {"endpoint": payload["subscription"]["endpoint"]},
        )
        self.assertEqual(delete_response["status"], 200)
        self.assertEqual(json.loads(delete_body), {"enabled": False})

    def test_wsgi_public_key_requires_server_configuration(self):
        import wsgi

        wsgi = importlib.reload(wsgi)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/api/push/public-key",
            "CONTENT_LENGTH": "0",
            "wsgi.input": io.BytesIO(),
        }
        captured = {}

        def start_response(status, headers):
            captured["status"] = int(status.split()[0])

        with patch.dict(
            os.environ,
            {
                "VAPID_PUBLIC_KEY": "",
                "VAPID_PRIVATE_KEY": "",
                "VAPID_SUBJECT": "",
            },
        ):
            body = b"".join(wsgi.application(environ, start_response))

        self.assertEqual(captured["status"], 503)
        self.assertIn(b"Push notifications are not configured", body)

        with patch.dict(
            os.environ,
            {
                "VAPID_PUBLIC_KEY": "public-key",
                "VAPID_PRIVATE_KEY": str(self.private_key),
                "VAPID_SUBJECT": "mailto:admin@example.com",
            },
        ):
            body = b"".join(wsgi.application(environ, start_response))

        self.assertEqual(captured["status"], 200)
        self.assertEqual(json.loads(body), {"public_key": "public-key"})

    def test_wsgi_scheduler_endpoint_requires_token(self):
        import wsgi

        wsgi = importlib.reload(wsgi)
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/api/push/send-due",
            "CONTENT_LENGTH": "0",
            "wsgi.input": io.BytesIO(),
        }
        captured = {}

        def start_response(status, headers):
            captured["status"] = int(status.split()[0])

        with patch.dict(os.environ, {"PUSH_SCHEDULER_TOKEN": "scheduler-secret"}):
            with patch.object(
                app,
                "send_due_reminders",
                return_value={"sent": 0, "failed": 0, "removed": 0},
            ) as send_due_reminders:
                body = b"".join(wsgi.application(environ, start_response))
                self.assertEqual(captured["status"], 401)
                send_due_reminders.assert_not_called()

                environ["HTTP_AUTHORIZATION"] = "Bearer scheduler-secret"
                body = b"".join(wsgi.application(environ, start_response))

        self.assertEqual(captured["status"], 200)
        self.assertEqual(json.loads(body), {"sent": 0, "failed": 0, "removed": 0})
        send_due_reminders.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
