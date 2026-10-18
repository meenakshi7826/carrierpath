"""WSGI entry point for PythonAnywhere deployment."""

import json
import sqlite3
from http import HTTPStatus
from urllib.parse import unquote

import app as carrierpath


# PythonAnywhere imports this module to obtain the callable named `application`.
carrierpath.initialize_database()


def _response(start_response, status, payload, content_type="application/json; charset=utf-8"):
    body = payload if isinstance(payload, bytes) else json.dumps(
        payload, ensure_ascii=False
    ).encode("utf-8")
    phrase = HTTPStatus(status).phrase
    start_response(
        f"{status} {phrase}",
        [
            ("Content-Type", content_type),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
        ],
    )
    return [body]


def _recent_recommendations():
    """Return summaries only, not the submitted education or skills details."""
    with sqlite3.connect(carrierpath.DATABASE) as connection:
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
    return {"recommendations": history}


def application(environ, start_response):
    """Serve the same page and JSON endpoints through PythonAnywhere's WSGI server."""
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = unquote(environ.get("PATH_INFO", "/"))

    if method == "GET" and path in {"/", "/index.html"}:
        try:
            page = (carrierpath.ROOT / "index.html").read_bytes()
        except OSError:
            return _response(start_response, 500, {"error": "Could not load the website."})
        return _response(start_response, 200, page, "text/html; charset=utf-8")

    if method == "GET" and path == "/api/health":
        return _response(start_response, 200, {"status": "ok"})

    if method == "GET" and path == "/api/recommendations":
        try:
            history = _recent_recommendations()
        except sqlite3.Error:
            return _response(
                start_response, 500, {"error": "Could not load saved guidance."}
            )
        return _response(start_response, 200, history)

    if method == "POST" and path == "/api/recommendations":
        try:
            content_length = int(environ.get("CONTENT_LENGTH") or "0")
        except ValueError:
            return _response(
                start_response, 400, {"error": "Invalid Content-Length header."}
            )

        if content_length <= 0 or content_length > carrierpath.MAX_BODY_BYTES:
            return _response(
                start_response, 413, {"error": "Request body is missing or too large."}
            )

        try:
            request_body = environ["wsgi.input"].read(content_length)
            payload = json.loads(request_body)
            profile = carrierpath.normalize_profile(payload)
            recommendation = carrierpath.create_recommendation(profile)
            record = carrierpath.save_recommendation(profile, recommendation)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            return _response(start_response, 400, {"error": str(error)})
        except sqlite3.Error:
            return _response(
                start_response, 500, {"error": "Could not save the recommendation."}
            )
        return _response(
            start_response, 201, {**record, "recommendation": recommendation}
        )

    if path.startswith("/api/"):
        return _response(start_response, 404, {"error": "Not found."})

    return _response(
        start_response,
        405 if method not in {"GET", "POST"} else 404,
        {"error": "Method not allowed." if method not in {"GET", "POST"} else "Not found."},
    )
