"""Database protections: append-only logs, retention, backup and restore, and
migration rollback. Creates a scratch database, gabai_review, and drops it at
the end; the real local database is never touched. Run it with the backend's
Python (backend/.venv) because it calls Alembic and the retention module."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
DB = "gabai_review"
results = []


def psql(sql, db=DB):
    p = subprocess.run(["docker", "exec", "gabai-db", "psql", "-U", "gabai", "-d", db,
                        "-v", "ON_ERROR_STOP=1", "-Atc", sql], capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def check(label, got, want):
    ok = got == want
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {label}: got {got!r}" + ("" if ok else f", want {want!r}"))


def refused(sql):
    code, out = psql(sql)
    return code != 0 and "append-only" in out


def retention(apply, env):
    e = dict(os.environ, POSTGRES_DB=DB, **env)
    args = [PY, "-m", "app.retention"] + (["--apply"] if apply else [])
    p = subprocess.run(args, cwd=ROOT / "backend", env=e, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


# ---- scratch database ----------------------------------------------------------
subprocess.run(["docker", "exec", "gabai-db", "sh", "-c",
                f"dropdb -U gabai --if-exists gabai_restore; dropdb -U gabai --if-exists {DB}; createdb -U gabai {DB}"],
               capture_output=True, text=True)
up = subprocess.run([PY, "-m", "alembic", "upgrade", "head"], cwd=ROOT / "backend",
                    env=dict(os.environ, POSTGRES_DB=DB), capture_output=True, text=True)
if up.returncode:
    print(up.stdout + up.stderr)
    raise SystemExit("could not build the scratch database")

# ---- seed ----------------------------------------------------------------------
OLD = "now() - interval '400 days'"
seed = f"""
INSERT INTO users (id,email,hashed_password,is_active,is_superuser,is_verified,full_name,role,approval_status,residence,deactivated_at)
VALUES
 ('11111111-1111-1111-1111-111111111111','active.old@x.test','h',true,false,true,'Active With Old Request','citizen','approved','Purok 1',NULL),
 ('22222222-2222-2222-2222-222222222222','deact.old@x.test','h',false,false,true,'Deactivated Long Ago','citizen','approved','Purok 2',{OLD}),
 ('33333333-3333-3333-3333-333333333333','rejected.old@x.test','h',true,false,true,'Rejected Long Ago','citizen','rejected','Purok 3',NULL),
 ('44444444-4444-4444-4444-444444444444','deact.new@x.test','h',false,false,true,'Deactivated Recently','citizen','approved','Purok 4',now() - interval '5 days'),
 ('55555555-5555-5555-5555-555555555555','staff.old@x.test','h',false,false,true,'Staff Deactivated Long Ago','staff','approved',NULL,{OLD});
INSERT INTO requests (id,reference_number,citizen_id,description,status,created_at,updated_at,resolved_at)
VALUES (1,'GAB-2025-00001','11111111-1111-1111-1111-111111111111','may butas sa harap ng bahay ko sa Purok 1','resolved',{OLD},{OLD},{OLD}),
       (2,'GAB-2026-00002','11111111-1111-1111-1111-111111111111','bagong reklamo, bukas pa','in_progress',now(),now(),NULL);
INSERT INTO status_history_entries (request_id,from_status,to_status,note,created_at)
VALUES (1,'in_progress','resolved','Naayos na po, salamat kay Mang Jose',{OLD}),
       (2,NULL,'submitted',NULL,now());
INSERT INTO attachments (request_id,filename,stored_path,mime_type,size_bytes) VALUES (1,'butas.png','review_test.png','image/png',4);
INSERT INTO audit_log_entries (actor_id,action,object_type,object_id,detail,ip_address,created_at)
VALUES (NULL,'user.rejected','user','33333333-3333-3333-3333-333333333333',NULL,'10.0.0.9',{OLD}),
       (NULL,'request.status_changed','request','1','{{"from":"in_progress","to":"resolved"}}','10.0.0.8',{OLD}),
       (NULL,'request.status_changed','request','2',NULL,'10.0.0.7',now());
INSERT INTO notifications (user_id,request_id,reference_number,message,is_read) VALUES ('22222222-2222-2222-2222-222222222222',NULL,NULL,'hello',false);
"""
code, out = psql(seed)
check("test rows load", code, 0)
if code:
    print(out[:800])
    raise SystemExit(1)
(ROOT / "backend" / "uploads").mkdir(parents=True, exist_ok=True)
(ROOT / "backend" / "uploads" / "review_test.png").write_bytes(b"test")

# ---- triggers ------------------------------------------------------------------
check("audit: edit action refused", refused("UPDATE audit_log_entries SET action='x' WHERE object_id='2'"), True)
check("audit: delete refused", refused("DELETE FROM audit_log_entries WHERE object_id='2'"), True)
check("audit: truncate refused", refused("TRUNCATE audit_log_entries"), True)
check("audit: clearing IP and changing action together refused",
      refused("UPDATE audit_log_entries SET ip_address=NULL, action='x' WHERE object_id='2'"), True)
check("history: edit status refused", refused("UPDATE status_history_entries SET to_status='closed' WHERE request_id=2"), True)
check("history: delete refused", refused("DELETE FROM status_history_entries WHERE request_id=2"), True)
check("history: truncate refused", refused("TRUNCATE status_history_entries"), True)
check("history: rewriting a note to other text refused",
      refused("UPDATE status_history_entries SET note='someone rewrote this' WHERE request_id=1"), True)
code, out = psql("BEGIN; UPDATE status_history_entries SET note='[Removed after the retention period]' WHERE request_id=1; ROLLBACK;")
check("history: note to the removal marker allowed", code, 0)
code, out = psql("BEGIN; UPDATE status_history_entries SET note=NULL WHERE request_id=1; ROLLBACK;")
check("history: clearing a note allowed", code, 0)

# ---- retention -----------------------------------------------------------------
env = {"RETENTION_REQUEST_DAYS": "30", "RETENTION_ACCOUNT_DAYS": "30", "RETENTION_IP_DAYS": "30"}
code, out = retention(False, {})
check("no periods set: nothing checked", "No retention period is set" in out, True)
code, out = retention(False, env)
check("dry run exits cleanly", code, 0)
print("   dry run said:", out.splitlines()[-2] if out else out)
check("dry run changed nothing (description intact)",
      psql("select description from requests where id=1")[1], "may butas sa harap ng bahay ko sa Purok 1")
code, out = retention(True, env)
check("apply exits cleanly", code, 0)
print("   apply said:", out.splitlines()[-1] if out else out)
check("old resolved request redacted", psql("select description, redacted_at is not null from requests where id=1")[1],
      "[Removed after the retention period]|t")
check("live request untouched", psql("select description, redacted_at is null from requests where id=2")[1],
      "bagong reklamo, bukas pa|t")
check("old request keeps reference, status, category fields",
      psql("select reference_number, status from requests where id=1")[1], "GAB-2025-00001|resolved")
check("status note replaced by marker", psql("select note from status_history_entries where request_id=1")[1],
      "[Removed after the retention period]")
check("attachment row removed", psql("select count(*) from attachments")[1], "0")
check("attachment file removed", (ROOT / "backend" / "uploads" / "review_test.png").exists(), False)
check("deactivated-long-ago citizen anonymized",
      psql("select full_name, residence is null, anonymized_at is not null, is_active from users where id='22222222-2222-2222-2222-222222222222'")[1],
      "Removed account|t|t|f")
check("its notifications removed", psql("select count(*) from notifications where user_id='22222222-2222-2222-2222-222222222222'")[1], "0")
check("rejected-long-ago citizen anonymized",
      psql("select full_name from users where id='33333333-3333-3333-3333-333333333333'")[1], "Removed account")
check("recently deactivated citizen kept",
      psql("select full_name from users where id='44444444-4444-4444-4444-444444444444'")[1], "Deactivated Recently")
check("staff never anonymized",
      psql("select full_name from users where id='55555555-5555-5555-5555-555555555555'")[1], "Staff Deactivated Long Ago")
check("active citizen with a live request kept",
      psql("select full_name from users where id='11111111-1111-1111-1111-111111111111'")[1], "Active With Old Request")
check("old IPs cleared, recent kept",
      psql("select string_agg(coalesce(host(ip_address::inet),'NULL'), ',' order by created_at) from audit_log_entries where action<>'retention.applied'")[1],
      "NULL,NULL,10.0.0.7")
check("audit rows all still there", psql("select count(*) from audit_log_entries where action<>'retention.applied'")[1], "3")
check("retention.applied logged once", psql("select count(*) from audit_log_entries where action='retention.applied'")[1], "1")
code, out = retention(True, env)
check("second run finds nothing, logs nothing", ("Nothing is past" in out,
      psql("select count(*) from audit_log_entries where action='retention.applied'")[1]), (True, "1"))

# ---- backup and restore ---------------------------------------------------------
p = subprocess.run(["docker", "exec", "gabai-db", "sh", "-c",
                    f"pg_dump -U gabai -d {DB} -Fc > /tmp/review.dump && dropdb -U gabai --if-exists gabai_restore "
                    "&& createdb -U gabai gabai_restore && pg_restore -U gabai -d gabai_restore /tmp/review.dump"],
                   capture_output=True, text=True)
check("dump and restore into an empty database", p.returncode, 0)
tables = ["users", "requests", "status_history_entries", "audit_log_entries", "notifications", "categories", "attachments"]
orig = [psql(f"select count(*) from {t}")[1] for t in tables]
rest = [psql(f"select count(*) from {t}", db="gabai_restore")[1] for t in tables]
check("restored row counts match every table", rest, orig)
code, out = psql("DELETE FROM audit_log_entries", db="gabai_restore")
check("append-only protection survives restore", code != 0 and "append-only" in out, True)

# ---- downgrade and back ----------------------------------------------------------
e = dict(os.environ, POSTGRES_DB=DB)
d = subprocess.run([PY, "-m", "alembic", "downgrade", "c7e2a5f18b04"], cwd=ROOT / "backend", env=e, capture_output=True, text=True)
check("downgrade to before the append-only triggers", d.returncode, 0)
check("triggers gone after downgrade", psql("select count(*) from pg_trigger where not tgisinternal")[1], "0")
u = subprocess.run([PY, "-m", "alembic", "upgrade", "head"], cwd=ROOT / "backend", env=e, capture_output=True, text=True)
head = subprocess.run([PY, "-m", "alembic", "heads"], cwd=ROOT / "backend", env=e, capture_output=True, text=True).stdout.split()[0]
check("upgrade again", (u.returncode, psql("select version_num from alembic_version")[1]), (0, head))

print(f"\n{sum(results)}/{len(results)} checks as expected")

subprocess.run(["docker", "exec", "gabai-db", "sh", "-c",
                f"dropdb -U gabai --if-exists gabai_restore; dropdb -U gabai --if-exists {DB}"],
               capture_output=True, text=True)
