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

1. Create a new, private GitHub repository for this site and add only `app.py`, `index.html`, `schema.sql`, `wsgi.py`, `requirements.txt`, `README.md`, and `.gitignore`. Do not upload `.venv`, `carrierpath.sqlite3`, or the other folders in your website directory.
2. In Render, choose **New** > **Web Service**, connect the GitHub repository, and select the free instance type.
3. Set the build command to `pip install -r requirements.txt` and the start command to `gunicorn wsgi:application --bind 0.0.0.0:$PORT`.
4. Create the service and wait for the deploy to finish. Open the `onrender.com` URL shown in the Render dashboard and test both forms.

The app saves submitted choices in SQLite. Render's free web services use an ephemeral filesystem, so saved guidance history can be lost when the service restarts or redeploys. Use persistent storage or a hosted database if you need submissions to survive. The site does not ask for names or email addresses; visitors should not enter sensitive personal information.

## Publish on PythonAnywhere

The backend needs a Python web host. PythonAnywhere runs it through `wsgi.py`; the local `app.py` server is for development.

1. Create a PythonAnywhere account and open its **Web** tab.
2. Choose **Add a new web app**, select a Python version supported by your account, and choose **Manual configuration**.
3. In the **Files** tab, create a folder such as `/home/yourusername/carrierpath`.
4. Upload `app.py`, `index.html`, `schema.sql`, and `wsgi.py` into that folder. Do not upload `.venv` or `carrierpath.sqlite3`; the database will be created on the server.
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

## API

- `GET /api/health` checks that the service is running.
- `POST /api/recommendations` validates a submitted profile, creates a guidance response, and saves it in SQLite.
- `GET /api/recommendations` returns the ten most recent saved guidance sessions.

The backend stores the selected education, skills, interests, goals, and generated recommendation. It does not request a name, email address, or other account details. Review the privacy and storage limitations above before sharing a public deployment.

## Free learning channels

The Skills section links to these YouTube channels:

- [CodeWithHarry](https://www.youtube.com/@CodeWithHarry) for Python and web development.
- [Apna College](https://www.youtube.com/@ApnaCollegeOfficial) for programming and computer-science lessons.

Channel content can change over time. Treat videos as a starting point: write code yourself, build small projects, and check current documentation when you get stuck.
