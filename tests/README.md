# Tests

Functional tests that drive the API the way the screens do, as a resident, a
staff member and an administrator, and check each response and the rows it
leaves in the database. The manual test cases in the paper's appendix cover the
same functions through the browser.

## What each suite covers

| Script | Covers | Checks |
|---|---|---|
| `functional/accounts_and_passwords.py` | Sign-up, name and password rules, admin-created accounts, temporary passwords, admin reset | 34 |
| `functional/resident_approval.py` | Purok or street at sign-up, pending accounts, staff approval and turning down | 33 |
| `functional/email_links.py` | Email confirmation and password reset links | 29 |
| `functional/request_workflow.py` | Submission, classification and routing, attachments, access control, status updates, notifications, reclassification, requests left unclassified, administrator functions, routing to deactivated accounts | 65 |
| `functional/terms_site_categories.py` | Terms acceptance, site settings and logo, category management | 58 |
| `functional/database_protections.py` | Append-only logs, retention, backup and restore, migration rollback | 37 |

## Setup on a fresh clone

You need Docker Desktop, Python 3.12 and the two classifier model folders
(`category-onnx` and `urgency-onnx`, about 266 MiB each). The models aren't in
the repository; get them from Justin and put them in `backend/models/`.

1. Copy `.env.example` to `.env` in the repository root and fill in:
   - `SEED_ADMIN_EMAIL`: a normal address such as `admin@example.com`. A
     `.local` address fails the email check.
   - `SEED_ADMIN_PASSWORD` and `SEED_DEMO_PASSWORD`: any passwords that meet
     the password rules.
   - `SEED_DEMO=1`
   - Leave `RESEND_API_KEY` empty, `ENVIRONMENT=development` and
     `PUBLIC_URL=http://localhost:5173`. No email is sent, and the suites read
     the links from the development log instead.
   - Don't put quotes around values.
2. Start the database from the repository root: `docker compose up -d`
3. Make the backend's Python environment, in `backend/`:
   ```bash
   python -m venv .venv
   .venv/Scripts/pip install -r requirements.txt
   ```
   (`.venv/bin/pip` on macOS or Linux.)
4. Still in `backend/`, apply the migrations and seed the accounts:
   ```bash
   .venv/Scripts/python -m alembic upgrade head
   .venv/Scripts/python -m app.seed
   ```
5. Start the API on `127.0.0.1:8000` and leave it running: `.venv/Scripts/python run.py`

## Running

From the repository root, in a second terminal:

```bash
backend/.venv/Scripts/python tests/functional/accounts_and_passwords.py
backend/.venv/Scripts/python tests/functional/resident_approval.py
backend/.venv/Scripts/python tests/functional/email_links.py
backend/.venv/Scripts/python tests/functional/request_workflow.py
backend/.venv/Scripts/python tests/functional/terms_site_categories.py
backend/.venv/Scripts/python tests/functional/database_protections.py
```

Each prints one PASS or FAIL line per check and a total at the end. To keep a
record, send each one to a dated file, for example
`... request_workflow.py > results-2026-10-01-request_workflow.txt`.

## Notes

- The suites create their own accounts and requests with a timestamp in the
  email, so they can be run again. Test data is kept, not deleted.
- `terms_site_categories.py` switches categories off and on and changes the
  site details, then puts them back. If it stops partway, check Site settings
  and switch any category back on by hand.
- `request_workflow.py` needs at least one of its six requests to be routed;
  with the current model five are. Two of its checks run only when the first
  request is routed (the assigned staff member can open it, the other one
  can't), so the total can be 63 instead of 65. It switches routing to a test
  account and back; if it stops partway, check Routing.
- `database_protections.py` works on a scratch database, `gabai_review`, which it
  creates and drops. It also restores a backup into `gabai_restore` to compare row
  counts. The real local database is not touched.
- `database_protections.py` and `email_links.py` import the backend, so run
  them with the backend's Python as shown above.

## Load test

`load/load_test.js` measures response times on the deployed site with k6.
Install it on Windows with `winget install k6 --source winget`. The command is at
the top of the file. It needs a staff account and an approved resident account
made for testing, and it creates 10 requests marked LOAD TEST, which staff close
afterwards.

`load/stress_test.js` is read-only. It steps from 20 to 40 to 60 staff sessions,
one minute each, and stops early if more than 5% of requests fail. Run both
outside office hours. The full procedure is in the group's test plan.
