Question Paper Archive --- Python Backend
A FastAPI and SQLite backend for the Question Paper Archive. It provides public paper access, PDF delivery, and protected admin operations.
Features
FastAPI REST API
SQLite database for paper records, administrator accounts, and sessions
Admin login and logout using HTTP-only session cookies
Public paper listing and individual paper details
PDF viewing and downloading
Admin dashboard statistics
Create, update, and delete paper records
PDF upload validation with a 20 MB limit
Password hashing using scrypt
Requirements
Python 3.10 or newer
pip
Project structure
python_backend_conversion/
├── app.py
├── requirements.txt
├── .env.example
└── README.md
The application creates its database and uploaded-file storage under the configured data directory.
Local setup
Extract the backend ZIP.
Open a terminal in the backend project directory.
Create and activate a virtual environment:
python -m venv .venv
Windows:
.venv\Scripts\activate
macOS/Linux:
source .venv/bin/activate
Install dependencies:
pip install -r requirements.txt
Copy .env.example to .env and configure the values.
Start the API:
uvicorn app:app --host 0.0.0.0 --port 8000
The API will be available at http://localhost:8000. FastAPI's interactive API documentation is normally available at /docs.
Environment variables
Variable                            Purpose
ADMIN_EMAIL                       Initial administrator email
ADMIN_PASSWORD                    Initial administrator password
SECRET_KEY                        Secret used to protect session data; replace the example value
COOKIE_SECURE                     Set to true when serving the backend over HTTPS
DATA_DIR                          Directory used for the SQLite database and uploaded PDFs
CORS_ORIGINS                      Comma-separated list of permitted frontend origins
Use strong, unique production credentials. Do not commit .env or secrets to source control.
API endpoints
General and authentication
Method                  Endpoint                      Description
GET                   /api/health                 Health check
GET                   /api/session                Check the current session
POST                  /api/auth/login             Administrator login
POST                  /api/auth/logout            End the current session
POST                  /api/auth/forgot-password   Placeholder endpoint; email-based recovery is not implemented
Public papers
Method   Endpoint                  Description
GET    /api/papers             List papers GET    /api/papers/{id}        Get paper details GET    /api/papers/{id}/file   View or download the paper PDF
Admin
Method     Endpoint                   Description
GET      /api/admin/dashboard     Get dashboard information GET      /api/admin/stats         Get statistics POST     /api/admin/papers        Create a paper and upload its PDF PUT      /api/admin/papers/{id}   Update a paper DELETE   /api/admin/papers/{id}   Delete a paper
Admin endpoints require an authenticated administrator session.
Connect the frontend
Set the frontend's API base URL to the deployed backend URL. In the supplied frontend, update API_BASE in assets/app.js from the local development URL to your backend's HTTPS URL.
The frontend must send requests with credentials enabled so the browser can include the session cookie.
Cross-domain cookie configuration
When the frontend and backend use different domains (for example, Netlify and Render), browser cookie restrictions may prevent the admin session from working with the default SameSite=Lax setting.
For a cross-site deployment, configure the backend cookie as SameSite=None; Secure, serve both sites over HTTPS, and configure credentialed CORS for the exact frontend origin. Do not use a wildcard origin with credentialed requests. Alternatively, use a same-site custom domain or reverse proxy.
Deployment
The backend can be deployed to a Python hosting service such as Render.
Set the build/install command to pip install -r requirements.txt.
Set the start command to uvicorn app:app --host 0.0.0.0 --port $PORT.
Configure all required environment variables in the hosting provider's dashboard.
Set DATA_DIR to a persistent disk or volume path.
Ensure the hosting plan provides persistent storage if uploaded PDFs and SQLite data must survive redeployments.
A temporary or ephemeral filesystem can be cleared when the service restarts or redeploys. Do not rely on it for permanent paper storage.
Production security checklist
Use HTTPS.
Replace the default SECRET_KEY.
Set a strong administrator password.
Set COOKIE_SECURE=true for HTTPS deployments.
Restrict CORS_ORIGINS to the exact frontend origin(s).
Use persistent storage and backups for the database and PDFs.
Keep dependencies updated.
Never publish .env or administrator credentials.
Limitations
The forgot-password endpoint is only a placeholder; no email delivery or password-reset flow is included.
The backend is a functional Python implementation and is not a reconstruction of the original server source code.
Cookie settings may need adjustment depending on whether the frontend and backend share a site.
Troubleshooting
Admin login works locally but not after deployment - Check that the frontend API URL points to the deployed backend. - Confirm the frontend sends credentials. - Check CORS origins and cookie SameSite/Secure settings. - Confirm both sites use HTTPS for cross-site cookies.
Papers or PDFs disappear after redeployment - Configure a persistent disk or volume and set DATA_DIR to its mount path.
The API does not start - Confirm the Python version and that pip install -r requirements.txt completed. - Check the hosting logs for missing environment variables or startup errors.
License
Add your chosen license before distributing or publishing this project.