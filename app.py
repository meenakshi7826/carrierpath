import json
import hmac
import json
import os
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ROOT = Path(__file__).resolve().parent
DATABASE = Path(
    os.environ.get("CARRIERPATH_DATABASE", str(ROOT / "carrierpath.sqlite3"))
).expanduser().resolve()
MAX_BODY_BYTES = 16_384
PUSH_NOTIFICATION = {
    "title": "Time for your study session",
    "body": "Your planned study time is here. Take one small step today.",
    "url": "/#study",
}

ALLOWED = {
    # Only accept values offered by the forms; never trust browser-submitted choices.
    "education": {"school", "12th", "college", "graduate", "working"},
    "stream": {"science", "commerce", "arts", "other"},
    "interest": {
        "technology", "business", "creative", "helping", "healthcare",
        "government", "unknown", "tech", "health", "public",
    },
    "skills": {
        "beginner", "some", "advanced", "technology", "communication",
        "creative", "analysis", "care",
    },
    "goal": {"job", "business", "freelance", "study", "explore"},
    "budget": {"low", "medium", "high"},
}

CAREERS = {
    "technology": [
        {
            "title": "Web Developer",
            "description": "Build websites and web applications.",
            "skills": "HTML, CSS, JavaScript",
            "route": "Learn the basics, build 2–3 projects, then explore internships.",
            "streams": ["science", "commerce", "arts", "other"],
        },
        {
            "title": "Data Analyst",
            "description": "Use data to solve business problems.",
            "skills": "Excel, SQL, statistics",
            "route": "Learn spreadsheets and SQL, then complete a data project.",
            "streams": ["science", "commerce", "arts", "other"],
        },
        {
            "title": "IT Support Professional",
            "description": "Help people solve computer and network problems.",
            "skills": "Computer basics, troubleshooting, networking",
            "route": "Practise computer troubleshooting and explore recognized training.",
            "streams": ["science", "commerce", "arts", "other"],
        },
    ],
    "business": [
        {
            "title": "Accounting Professional",
            "description": "Work with accounts, records and financial information.",
            "skills": "Accounting, spreadsheets, attention to detail",
            "route": "Learn accounting fundamentals and check course eligibility.",
            "streams": ["commerce", "science", "arts", "other"],
        },
        {
            "title": "Digital Marketing",
            "description": "Help businesses reach customers online.",
            "skills": "Content, analytics, communication",
            "route": "Study marketing basics and build a sample campaign.",
            "streams": ["science", "commerce", "arts", "other"],
        },
        {
            "title": "Business Analyst",
            "description": "Understand business needs and help improve processes.",
            "skills": "Excel, communication, problem-solving",
            "route": "Practise spreadsheets and business case studies.",
            "streams": ["science", "commerce", "arts", "other"],
        },
    ],
    "creative": [
        {
            "title": "Graphic Designer",
            "description": "Create visual content for brands and businesses.",
            "skills": "Design fundamentals, typography, layout",
            "route": "Create sample posters and build a design portfolio.",
            "streams": ["science", "commerce", "arts", "other"],
        },
        {
            "title": "Content Writer",
            "description": "Create useful written content for different audiences.",
            "skills": "Writing, research, editing",
            "route": "Write sample articles and practise editing.",
            "streams": ["science", "commerce", "arts", "other"],
        },
        {
            "title": "Video Editor",
            "description": "Edit video content for online and professional use.",
            "skills": "Editing, storytelling, audio basics",
            "route": "Make sample videos and build a small portfolio.",
            "streams": ["science", "commerce", "arts", "other"],
        },
    ],
    "helping": [
        {
            "title": "Teacher or Tutor",
            "description": "Help others understand subjects and develop skills.",
            "skills": "Subject knowledge, patience, communication",
            "route": "Practise teaching and check relevant qualification requirements.",
            "streams": ["science", "commerce", "arts", "other"],
        },
        {
            "title": "Psychology Pathway",
            "description": "Explore human behaviour and psychology-related study.",
            "skills": "Listening, research, critical thinking",
            "route": "Research recognized degrees and professional qualification rules.",
            "streams": ["science", "commerce", "arts", "other"],
        },
        {
            "title": "Social Work",
            "description": "Support individuals and communities through organized services.",
            "skills": "Communication, empathy, problem-solving",
            "route": "Explore social science courses and practical volunteering.",
            "streams": ["science", "commerce", "arts", "other"],
        },
    ],
    "healthcare": [
        {
            "title": "Healthcare Professional",
            "description": "Explore healthcare and allied health career pathways.",
            "skills": "Biology fundamentals, communication, attention to detail",
            "route": "Check the specific course, science prerequisites and licensing rules.",
            "streams": ["science"],
        },
        {
            "title": "Biology and Life Sciences",
            "description": "Explore laboratory science, research and life-science careers.",
            "skills": "Biology, scientific reasoning, lab fundamentals",
            "route": "Compare recognized courses and their entry requirements.",
            "streams": ["science"],
        },
    ],
    "government": [
        {
            "title": "Government Exam Pathway",
            "description": "Explore eligible government recruitment examinations.",
            "skills": "General knowledge, reasoning, subject preparation",
            "route": "Choose exams based on age, qualification and official eligibility.",
            "streams": ["science", "commerce", "arts", "other"],
        },
        {
            "title": "Public Sector Career",
            "description": "Explore public-sector roles and relevant recruitment routes.",
            "skills": "Role-specific knowledge and exam preparation",
            "route": "Check official recruitment notices and qualification criteria.",
            "streams": ["science", "commerce", "arts", "other"],
        },
    ],
    "unknown": [
        {
            "title": "Explore Technology",
            "description": "Try a beginner computer or coding activity.",
            "skills": "Curiosity, logical thinking",
            "route": "Complete a small beginner project before deciding.",
            "streams": ["science", "commerce", "arts", "other"],
        },
        {
            "title": "Explore Business",
            "description": "Try budgeting, spreadsheets or a business case study.",
            "skills": "Planning, communication, problem-solving",
            "route": "Complete a simple budgeting or market-research exercise.",
            "streams": ["science", "commerce", "arts", "other"],
        },
        {
            "title": "Explore Creative Work",
            "description": "Try writing, design or video editing.",
            "skills": "Creativity, practice, communication",
            "route": "Complete a small creative project and reflect on the experience.",
            "streams": ["science", "commerce", "arts", "other"],
        },
    ],
}

PATHS = {
    "technology": {
        "title": "Technology & Digital Careers",
        "summary": "A possible fit if you enjoy solving problems with logic, software, and data.",
        "steps": [
            "Start with basic digital skills: spreadsheets, online research, and computer literacy.",
            "Explore web development, IT support, or data analytics through a beginner activity.",
            "Build two small projects and practise explaining your work.",
        ],
        "good_for": ["Coding", "Software", "Data", "IT support"],
    },
    "business": {
        "title": "Business & Finance Careers",
        "summary": "A possible fit if you enjoy planning, numbers, communication, and decision-making.",
        "steps": [
            "Learn spreadsheets, basic accounting, and business communication.",
            "Explore marketing, analysis, operations, or finance support.",
            "Practise with budgeting, planning, and presentation projects.",
        ],
        "good_for": ["Finance", "Marketing", "Management", "Entrepreneurship"],
    },
    "creative": {
        "title": "Creative & Media Careers",
        "summary": "A possible fit if you enjoy design, storytelling, writing, or visual communication.",
        "steps": [
            "Create two or three sample projects in design, writing, or video.",
            "Learn a suitable design, writing, or video-editing tool.",
            "Collect your work in a small portfolio and ask for feedback.",
        ],
        "good_for": ["Design", "Writing", "Content", "Media"],
    },
    "health": {
        "title": "Healthcare & Human-Centered Careers",
        "summary": "A possible fit if you enjoy helping people, scientific learning, and service.",
        "steps": [
            "Strengthen biology, chemistry, and communication fundamentals.",
            "Research recognized programs, prerequisites, and licensing requirements.",
            "Explore practical exposure through volunteering or supervised experiences.",
        ],
        "good_for": ["Healthcare", "Biology", "Allied health", "Care services"],
    },
    "public": {
        "title": "Public Service & Structured Career Paths",
        "summary": "A possible fit if you prefer structured roles and public-facing service.",
        "steps": [
            "Check official eligibility, age limits, and exam requirements.",
            "Build a realistic study routine for reasoning and relevant subjects.",
            "Use official recruitment notices as the source of current requirements.",
        ],
        "good_for": ["Government roles", "Public administration", "Policy", "Public service"],
    },
}

SKILL_TEXT = {
    "technology": "Your selected strength points toward technical and digital work.",
    "communication": "Your selected strength points toward communication-heavy and people-centered work.",
    "creative": "Your selected strength points toward design and creative storytelling.",
    "analysis": "Your selected strength points toward analytical, data, and process-based work.",
    "care": "Your selected strength points toward service-focused and people-helping work.",
    "beginner": "You can begin with introductory material and small practice projects.",
    "some": "Build on your current experience with a focused project or course.",
    "advanced": "Consider a portfolio project, internship, or role-specific specialization.",
}

GOAL_TEXT = {
    "job": "Prioritize practical skills and verified entry-level opportunities.",
    "freelance": "Build sample work first, then explore project-based opportunities carefully.",
    "business": "Research a real problem, test a small idea, and learn basic budgeting.",
    "study": "Compare recognized programs, eligibility, fees, and scholarships.",
    "explore": "Try a few small activities before making a major education or career decision.",
}

EDUCATION_TEXT = {
    "school": "At school level, explore options and check subject prerequisites before choosing courses.",
    "12th": "After secondary school, compare recognized courses and check each program's entry requirements.",
    "college": "As a college student, look for relevant projects, internships, and course options.",
    "graduate": "As a graduate, map your existing qualification to roles and identify any skill gaps.",
    "working": "For a career change, test the new field with a small project before investing in training.",
}


def initialize_database():
    # Reapplying CREATE TABLE IF NOT EXISTS makes startup safe for both new and existing databases.
    with closing(sqlite3.connect(DATABASE)) as connection:
        with connection:
            connection.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))


def get_vapid_configuration():
    public_key = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
    private_key = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    subject = os.environ.get("VAPID_SUBJECT", "").strip()
    if not public_key or not private_key or not subject:
        raise RuntimeError(
            "Push notifications are not configured. Set VAPID_PUBLIC_KEY, "
            "VAPID_PRIVATE_KEY, and VAPID_SUBJECT."
        )
    if not Path(private_key).is_file():
        raise RuntimeError("VAPID_PRIVATE_KEY must point to the private PEM key file.")
    if not subject.startswith(("mailto:", "https://")):
        raise RuntimeError("VAPID_SUBJECT must be a mailto: address or HTTPS URL.")
    return public_key, private_key, subject


def has_valid_scheduler_token(authorization):
    expected_token = os.environ.get("PUSH_SCHEDULER_TOKEN", "")
    if not expected_token or not isinstance(authorization, str):
        return False
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return False
    return hmac.compare_digest(authorization[len(prefix):], expected_token)


def validate_push_endpoint(endpoint):
    if not isinstance(endpoint, str) or not endpoint or len(endpoint) > 4096:
        raise ValueError("A valid push subscription endpoint is required.")

    parsed = urlparse(endpoint)
    hostname = (parsed.hostname or "").lower()
    trusted_host = (
        hostname in {"fcm.googleapis.com", "updates.push.services.mozilla.com"}
        or hostname == "notify.windows.com"
        or hostname.endswith(".notify.windows.com")
        or hostname.endswith(".push.apple.com")
    )
    try:
        valid_port = parsed.port in {None, 443}
    except ValueError:
        valid_port = False

    if (
        parsed.scheme != "https"
        or not trusted_host
        or parsed.username is not None
        or parsed.password is not None
        or not valid_port
    ):
        raise ValueError("The push subscription endpoint is not supported.")
    return endpoint


def validate_push_subscription(payload):
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")

    subscription = payload.get("subscription")
    if not isinstance(subscription, dict):
        raise ValueError("A valid push subscription is required.")
    endpoint = validate_push_endpoint(subscription.get("endpoint"))
    keys = subscription.get("keys")
    if not isinstance(keys, dict):
        raise ValueError("Push subscription keys are required.")
    auth = keys.get("auth")
    p256dh = keys.get("p256dh")
    if not all(isinstance(value, str) and 1 <= len(value) <= 256 for value in (auth, p256dh)):
        raise ValueError("Push subscription keys are invalid.")

    reminder_time = payload.get("reminder_time")
    if not isinstance(reminder_time, str) or not re.fullmatch(
        r"(?:[01]\d|2[0-3]):[0-5]\d", reminder_time
    ):
        raise ValueError("Choose a valid reminder time.")

    timezone_name = payload.get("timezone")
    if not isinstance(timezone_name, str) or len(timezone_name) > 100:
        raise ValueError("Choose a valid time zone.")
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Choose a valid time zone.") from None

    return (
        {
            "endpoint": endpoint,
            "keys": {"auth": auth, "p256dh": p256dh},
        },
        reminder_time,
        timezone_name,
    )


def save_push_subscription(payload):
    subscription, reminder_time, timezone_name = validate_push_subscription(payload)
    with closing(sqlite3.connect(DATABASE)) as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO push_subscriptions
                    (endpoint, subscription_json, reminder_time, timezone, enabled)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(endpoint) DO UPDATE SET
                    subscription_json = excluded.subscription_json,
                    reminder_time = excluded.reminder_time,
                    timezone = excluded.timezone,
                    enabled = 1
                """,
                (
                    subscription["endpoint"],
                    json.dumps(subscription),
                    reminder_time,
                    timezone_name,
                ),
            )
    return {"enabled": True, "reminder_time": reminder_time, "timezone": timezone_name}


def remove_push_subscription(payload):
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    endpoint = validate_push_endpoint(payload.get("endpoint"))
    with closing(sqlite3.connect(DATABASE)) as connection:
        with connection:
            connection.execute(
                "DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,)
            )
    return {"enabled": False}


def send_due_reminders(now=None, push_sender=None):
    _, private_key, subject = get_vapid_configuration()
    if push_sender is None:
        from pywebpush import WebPushException, webpush

        push_sender = webpush
    else:
        from pywebpush import WebPushException

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        raise ValueError("The current time must include a time zone.")

    with closing(sqlite3.connect(DATABASE)) as connection:
        subscriptions = connection.execute(
            """
            SELECT endpoint, subscription_json, reminder_time, timezone, last_sent_date
            FROM push_subscriptions
            WHERE enabled = 1
            """
        ).fetchall()

    sent = 0
    failed = 0
    removed = 0
    for endpoint, serialized, reminder_time, timezone_name, last_sent_date in subscriptions:
        local_time = current_time.astimezone(ZoneInfo(timezone_name))
        local_date = local_time.date().isoformat()
        if local_time.strftime("%H:%M") < reminder_time or last_sent_date == local_date:
            continue

        try:
            push_headers = {}
            ttl = 3600
            hostname = (urlparse(endpoint).hostname or "").lower()
            if hostname == "notify.windows.com" or hostname.endswith(
                ".notify.windows.com"
            ):
                push_headers = {
                    "X-WNS-Type": "wns/raw",
                    "Content-Type": "application/octet-stream",
                }
                ttl = 600
            push_sender(
                subscription_info=json.loads(serialized),
                data=json.dumps(PUSH_NOTIFICATION),
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
                headers=push_headers,
                ttl=ttl,
            )
        except WebPushException as error:
            failed += 1
            if error.response is not None and error.response.status_code in {404, 410}:
                with closing(sqlite3.connect(DATABASE)) as connection:
                    with connection:
                        connection.execute(
                            "DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,)
                        )
                removed += 1
            print(
                f"Push delivery failed with status {error.response.status_code if error.response else 'unknown'}.",
                file=sys.stderr,
            )
            continue

        with closing(sqlite3.connect(DATABASE)) as connection:
            with connection:
                connection.execute(
                    """
                    UPDATE push_subscriptions
                    SET last_sent_date = ?
                    WHERE endpoint = ?
                    """,
                    (local_date, endpoint),
                )
        sent += 1

    return {"sent": sent, "failed": failed, "removed": removed}


def normalize_profile(payload):
    """Validate form input and translate short UI aliases into canonical categories."""
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")

    mode = payload.get("mode")
    if not isinstance(mode, str) or mode not in {"advisor", "career"}:
        raise ValueError("Mode must be 'advisor' or 'career'.")

    profile = {"mode": mode}
    fields = ["education", "interest", "skills", "goal"]
    if mode == "career":
        # The detailed Career Finder also needs a school stream and budget preference.
        fields.extend(["stream", "budget"])

    for field in fields:
        value = payload.get(field)
        if not isinstance(value, str) or value not in ALLOWED[field]:
            raise ValueError(f"Choose a valid {field}.")
        profile[field] = value

    if mode == "advisor":
        # Keep older/shorter values from the clickable chips compatible with our rule tables.
        profile["interest"] = {
            "tech": "technology",
            "health": "health",
            "public": "public",
        }.get(profile["interest"], profile["interest"])
        if profile["interest"] not in PATHS:
            raise ValueError("Choose a valid career interest.")
    return profile


def create_recommendation(profile):
    """Apply the local guidance rules to a validated profile; no external AI is called."""
    if profile["mode"] == "advisor":
        path = PATHS[profile["interest"]]
        recommendation = {
            "title": path["title"],
            "summary": path["summary"],
            "skill_text": SKILL_TEXT[profile["skills"]],
            "goal_text": GOAL_TEXT[profile["goal"]],
            "education_text": EDUCATION_TEXT[profile["education"]],
            "steps": path["steps"],
            "good_for": path["good_for"],
        }
        return recommendation

    interest = profile["interest"]
    stream = profile["stream"]
    # Filter out paths that require a different school stream; offer exploration ideas
    # rather than returning an empty result when no listed path matches.
    careers = [
        career for career in CAREERS.get(interest, CAREERS["unknown"])
        if stream in career["streams"]
    ]
    if not careers:
        careers = CAREERS["unknown"]

    recommendation = {
        "careers": careers,
        "goal_text": GOAL_TEXT[profile["goal"]],
        "education_text": EDUCATION_TEXT[profile["education"]],
        "beginner_tip": (
            "Start with free introductory lessons and small projects before paying for a course."
            if profile["skills"] == "beginner" else ""
        ),
        "budget_tip": (
            "Compare public institutions, scholarships, free learning resources, and recognized low-cost courses."
            if profile["budget"] == "low" else ""
        ),
        "education": profile["education"],
        "stream": profile["stream"],
    }
    return recommendation


def save_recommendation(profile, recommendation):
    with sqlite3.connect(DATABASE) as connection:
        # Placeholders keep submitted values separate from SQL instructions.
        cursor = connection.execute(
            """
            INSERT INTO guidance_sessions
                (mode, education, stream, interest, skills, goal, budget, recommendation_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile["mode"],
                profile["education"],
                profile.get("stream"),
                profile["interest"],
                profile["skills"],
                profile["goal"],
                profile.get("budget"),
                json.dumps(recommendation, ensure_ascii=False),
            ),
        )
        row = connection.execute(
            "SELECT created_at FROM guidance_sessions WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return {"id": cursor.lastrowid, "created_at": row[0]}


class CarrierPathHandler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        """Serve the page and read-only endpoints using the same local server."""
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            try:
                body = (ROOT / "index.html").read_bytes()
            except OSError:
                self.send_json(500, {"error": "Could not load the website."})
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/service-worker.js":
            try:
                body = (ROOT / "service-worker.js").read_bytes()
            except OSError:
                self.send_json(500, {"error": "Could not load the service worker."})
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Service-Worker-Allowed", "/")
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/health":
            self.send_json(200, {"status": "ok"})
            return

        if path == "/api/push/public-key":
            try:
                public_key, _, _ = get_vapid_configuration()
            except RuntimeError as error:
                self.send_json(503, {"error": str(error)})
                return
            self.send_json(200, {"public_key": public_key})
            return

        if path == "/api/recommendations":
            with sqlite3.connect(DATABASE) as connection:
                rows = connection.execute(
                    """
                    SELECT id, created_at, mode, recommendation_json
                    FROM guidance_sessions
                    ORDER BY id DESC LIMIT 10
                    """
                ).fetchall()
            history = []
            for row_id, created_at, mode, serialized in rows:
                recommendation = json.loads(serialized)
                title = (
                    recommendation.get("title")
                    if mode == "advisor"
                    else recommendation["careers"][0]["title"]
                )
                history.append({
                    "id": row_id,
                    "created_at": created_at,
                    "mode": mode,
                    "title": title,
                })
            self.send_json(200, {"recommendations": history})
            return

        self.send_json(404, {"error": "Not found."})

    def do_POST(self):
        """Read one bounded JSON profile, validate it, generate advice, and persist it."""
        path = urlparse(self.path).path
        if path == "/api/push/send-due":
            if not has_valid_scheduler_token(self.headers.get("Authorization", "")):
                self.send_json(401, {"error": "Unauthorized."})
                return
            try:
                result = send_due_reminders()
            except RuntimeError as error:
                self.send_json(503, {"error": str(error)})
                return
            except sqlite3.Error:
                self.log_error("Database error while sending study reminders")
                self.send_json(500, {"error": "Could not send study reminders."})
                return
            self.send_json(200, result)
            return

        if path not in {"/api/recommendations", "/api/push/subscriptions"}:
            self.send_json(404, {"error": "Not found."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"error": "Invalid Content-Length header."})
            return
        if content_length <= 0 or content_length > MAX_BODY_BYTES:
            self.send_json(413, {"error": "Request body is missing or too large."})
            return

        try:
            # Validation and recommendation failures are client errors; storage failures
            # are handled separately below so they are not disguised as bad form input.
            request_body = self.rfile.read(content_length)
            payload = json.loads(request_body)
            if path == "/api/push/subscriptions":
                result = save_push_subscription(payload)
                self.send_json(201, result)
                return
            profile = normalize_profile(payload)
            recommendation = create_recommendation(profile)
            record = save_recommendation(profile, recommendation)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self.send_json(400, {"error": str(error)})
            return
        except sqlite3.Error:
            self.log_error("Database error while saving a recommendation")
            self.send_json(500, {"error": "Could not save the recommendation."})
            return

        self.send_json(201, {**record, "recommendation": recommendation})

    def do_DELETE(self):
        if urlparse(self.path).path != "/api/push/subscriptions":
            self.send_json(404, {"error": "Not found."})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"error": "Invalid Content-Length header."})
            return
        if content_length <= 0 or content_length > MAX_BODY_BYTES:
            self.send_json(413, {"error": "Request body is missing or too large."})
            return
        try:
            payload = json.loads(self.rfile.read(content_length))
            result = remove_push_subscription(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self.send_json(400, {"error": str(error)})
            return
        except sqlite3.Error:
            self.log_error("Database error while removing a push subscription")
            self.send_json(500, {"error": "Could not disable study reminders."})
            return
        self.send_json(200, result)

    def log_message(self, format_string, *args):
        print("%s - %s" % (self.address_string(), format_string % args))


def main():
    """Run the local server or send reminders due at the current time."""
    initialize_database()
    if len(sys.argv) > 1:
        if sys.argv[1:] != ["send-due-reminders"]:
            raise SystemExit("Usage: python app.py [send-due-reminders]")
        result = send_due_reminders()
        print(
            f"Study reminders sent: {result['sent']}; "
            f"failed: {result['failed']}; expired subscriptions removed: {result['removed']}."
        )
        if result["failed"]:
            return 1
        return 0

    server = ThreadingHTTPServer(("127.0.0.1", 8000), CarrierPathHandler)
    print("CarrierPath running at http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping CarrierPath.")
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
