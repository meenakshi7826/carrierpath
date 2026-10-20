# CarrierPath

CarrierPath is a small career-guidance website with a Python standard-library backend and a SQLite database. The recommendations are generated from built-in guidance rules; this starter does not call an external AI service.

## Run locally

1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Run:

   ```powershell
   python app.py
   ```

4. Open <http://127.0.0.1:8000>.

The server creates `carrierpath.sqlite3` and initializes its table from `schema.sql` on first launch. Stop it with Ctrl+C. Do not open `index.html` directly as a `file://` page when using the backend; the page needs to be served by the Python app.

## Publish on Render

Render can host the Python backend and provide a public `onrender.com` URL.

1. Create a new, private GitHub repository for this site and add `app.py`, `index.html`, `service-worker.js`, `schema.sql`, `wsgi.py`, `requirements.txt`, `README.md`, `.gitignore`, and `tests/test_push_notifications.py`. Do not upload `.venv`, `carrierpath.sqlite3`, or the other folders in your website directory.
2. In Render, choose **New** > **Web Service** and connect the GitHub repository.
3. Set the build command to `pip install -r requirements.txt` and the start command to `gunicorn wsgi:application --bind 0.0.0.0:$PORT`.
4. Create the service and wait for the deploy to finish. Open the `onrender.com` URL shown in the Render dashboard and test both forms.

The app saves submitted choices in SQLite. Render's free web services use an ephemeral filesystem, so saved guidance history can be lost when the service restarts or redeploys. Use persistent storage or a hosted database if you need submissions to survive. The site does not ask for names or email addresses; visitors should not enter sensitive personal information.

To retain submissions and push subscriptions on Render, attach a persistent disk to the web service, mount it at `/var/data`, and set `CARRIERPATH_DATABASE=/var/data/carrierpath.sqlite3`. Persistent disks may require a paid Render plan.

## Publish on PythonAnywhere

The backend needs a Python web host. PythonAnywhere runs it through `wsgi.py`; the local `app.py` server is for development.

1. Create a PythonAnywhere account and open its **Web** tab.
2. Choose **Add a new web app**, select a Python version supported by your account, and choose **Manual configuration**.
3. In the **Files** tab, create a folder such as `/home/yourusername/carrierpath`.
4. Upload `app.py`, `index.html`, `service-worker.js`, `schema.sql`, and `wsgi.py` into that folder. Do not upload `.venv` or `carrierpath.sqlite3`; the database will be created on the server.
5. Open the WSGI configuration file shown on the **Web** tab. Replace its contents with the following, substituting your PythonAnywhere username:

   ```python
   import sys

   project_directory = "/home/yourusername/carrierpath"
   if project_directory not in sys.path:
       sys.path.insert(0, project_directory)

   from wsgi import application
   ```

6. Save the WSGI file and click **Reload** on the Web tab.
7. Visit the web address shown on the Web tab. The form and saved-history API should use that same address.

The SQLite file is created beside `app.py`, so keep that project directory writable by your web app. Download a backup of `carrierpath.sqlite3` periodically if you need to keep submissions. The public site collects submitted education, interest, skills, goal, and budget choices; the site footer includes a privacy notice. Never upload account passwords, API keys, or your local virtual environment.

## Study reminders and push notifications

The Study Planner can send a daily push reminder at the visitor's chosen local time, including when the website is closed. Push reminders require an HTTPS deployment, a browser that supports push notifications, VAPID keys, persistent subscription storage, and a recurring server task. Local `http://127.0.0.1` can be used for browser testing, but public deployments must use HTTPS.

1. Install dependencies with `pip install -r requirements.txt`.
2. Generate a VAPID key pair in a private directory using the installed `vapid --gen` command. Keep `private_key.pem` out of the repository and restrict access to it. Keep using the same key pair; replacing it requires visitors to subscribe again.
3. Run `vapid --applicationServerKey` and set its output as `VAPID_PUBLIC_KEY`. Set `VAPID_PRIVATE_KEY` to the private PEM file path and `VAPID_SUBJECT` to a contact such as `mailto:admin@example.com`.
4. Configure those three environment variables on the web service. On Render, add `private_key.pem` as a Secret File and set `VAPID_PRIVATE_KEY=/etc/secrets/private_key.pem`. Never commit or share the private key.
5. Use persistent storage for `carrierpath.sqlite3`. Push subscriptions are stored in that database, so they are lost if a host's filesystem is ephemeral or the database is replaced.
6. Configure a scheduler to run every minute. On a host that runs the scheduler in the same environment and database as the app, run `python app.py send-due-reminders`. On Render, create a Cron Job that makes an authenticated POST request to the web service at `/api/push/send-due`; this avoids running the scheduler against a separate SQLite database.

For the Render Cron Job, generate a random scheduler token (for example, `python -c "import secrets; print(secrets.token_urlsafe(32))"`), then set `PUSH_SCHEDULER_TOKEN` to the same secret on both the web service and Cron Job. Also set `CARRIERPATH_BASE_URL` on the Cron Job to the web service's `https://...onrender.com` URL. Use this Cron Job command and schedule it to run once per minute:

```sh
curl -fsS -X POST \
  -H "Authorization: Bearer $PUSH_SCHEDULER_TOKEN" \
  "$CARRIERPATH_BASE_URL/api/push/send-due"
```

The endpoint only sends due reminders when the bearer token matches. Do not expose or commit the token. Render Cron Jobs do not share the web service's local files; the web service must use a persistent disk (or a shared external database) for subscriptions to survive restarts and deployments.

The server stores each opted-in browser's push endpoint and encryption keys, selected reminder time, and time zone. Visitors can disable reminders in the Study Planner. Push services may retain a notification until it is delivered or expires. Browser and operating-system support varies; some mobile browsers require visitors to install the site on their home screen.

## Learning guide

The Skills section links to channels for web development, Python, data analytics, and graphic design. Its durations are part-time estimates based on about four to five hours of learning per week; current video and playlist lengths may change. Follow one beginner playlist at a time and spend at least as much time practising as watching.

## API

- `GET /api/health` checks that the service is running.
- `POST /api/recommendations` validates a submitted profile, creates a guidance response, and saves it in SQLite.
- `GET /api/recommendations` returns the ten most recent saved guidance sessions.
- `GET /api/push/public-key`, `POST /api/push/subscriptions`, `DELETE /api/push/subscriptions`, and token-protected `POST /api/push/send-due` support browser push reminders.

The backend stores the selected education, skills, interests, goals, and generated recommendation. It does not request a name, email address, or other account details. Review the privacy and storage limitations above before sharing a public deployment.

## Free learning channels

The Skills section links to these YouTube channels:

- [CodeWithHarry](https://www.youtube.com/@CodeWithHarry) for Hindi Python and web development lessons.
- [freeCodeCamp.org](https://www.youtube.com/@freecodecamp) for English programming and web-development courses.
- [Apna College](https://www.youtube.com/@ApnaCollegeOfficial) for programming and computer-science lessons.
- [Alex The Analyst](https://www.youtube.com/@AlexTheAnalyst) for data analytics.
- [WsCube Tech](https://www.youtube.com/@WsCubeTech) for Hindi technology and data courses.
- [Canva](https://www.youtube.com/@Canva) and [Satori Graphics](https://www.youtube.com/@SatoriGraphics) for design tutorials and principles.

Channel content can change over time. Treat videos as a starting point: write code yourself, build small projects, and check current documentation when you get stuck.
