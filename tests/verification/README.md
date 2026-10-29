# Final-build verification

The checks the panel asked for after the October changes (paper Section 4.1, Tables 20A to 20C).
Generated from `cases.py` by `paper/build-scripts/make_verification_sheet.py`; the printable sheet has
blank result columns.

## A. Browser workflows

Environments: Chrome (Windows laptop); Edge (Windows laptop); Firefox (Windows laptop); Safari (macOS) (borrowed Mac, 24 October 2026); Safari (iPhone 13) (iPhone 13 with Safari); Chrome (Android, Poco F6) (Poco F6 with Chrome).

### V-01 Sign-up with purok or street and terms acceptance (Resident)

Run in: Chrome, Edge, Firefox, Safari (iPhone 13), Chrome (Android, Poco F6).

1. Open https://gabai.help and choose Register.
2. Enter a name, a new email (for example yourname+v01chrome@gmail.com), a purok or street and a password.
3. Try to submit with the Terms of Use and Privacy Notice box unticked.
4. Tick the box and submit. Open the Terms link.

Expected: The form will not submit until the box is ticked. The account is created and the screen says to confirm the email and wait for approval. The Terms page shows the version of 16 October 2026.

### V-02 Email confirmation, sign-in and password reset (Resident)

Run in: Chrome, Edge, Firefox, Safari (iPhone 13), Chrome (Android, Poco F6).

1. Open the confirmation link from the V-01 email in the same browser.
2. Sign in: the waiting screen shows until staff approve the account (V-11), then the resident home.
3. Sign out, choose Forgot password, open the reset link, set a new password.
4. Sign in with the old password, then with the new one.

Expected: The email is confirmed and the token after # disappears from the address bar. The old password is refused and the new one works.

### V-03 Submit a request with a place (Resident)

Run in: Chrome, Edge, Firefox, Safari (iPhone 13), Chrome (Android, Poco F6).

1. Open Report a concern. Type a description that starts with VERIFICATION TEST.
2. Under "Where is the problem? · Saan po ang problema?" choose a purok or street.
3. Submit, then open My requests and the new request.

Expected: A reference number GAB-YYYY-NNNNN shows at once. The request, its place and its description read as normal text. Chrome run only: the database check in the README shows the stored description starts with gabai:enc:.

### V-04 Attach a photo and a 2.8 MB PDF, then download them (Resident)

Run in: Chrome, Edge, Firefox, Safari (iPhone 13), Chrome (Android, Poco F6).

1. On a new VERIFICATION TEST request, attach a phone photo and the 2.8 MB PDF used for CB-24.
2. Submit. Open the request and download both files.
3. Desktop only: in PowerShell run Get-FileHash on the original PDF and on the downloaded PDF.

Expected: Both files upload and open. Desktop: the two PDF SHA-256 values are equal. (Photos are reduced in the browser before upload, so only the PDF can match exactly.) Note the result of the PDF on each phone.

### V-05 Follow a request; urgent once; notes from a linked report (Resident)

Run in: Chrome, Edge, Firefox, Safari (iPhone 13), Chrome (Android, Poco F6).

1. On an open VERIFICATION TEST request press "This is urgent · Urgent po ito" and give a reason.
2. Check whether the button can be pressed again.
3. After staff link the request to a main report and add a note (V-09, V-12), open it again.

Expected: The urgent flag is accepted once and the button does not come back. The linked request shows "Others reported the same problem", the main report's status and the staff note. Times are Philippine time.

### V-06 A referred request shows the agency (Resident)

Run in: Chrome, Edge, Firefox, Safari (iPhone 13), Chrome (Android, Poco F6).

1. After staff refer a VERIFICATION TEST request (V-10), open it as the resident.

Expected: The status reads Referred, with the agency's name and the contact details the administrator entered (V-13).

### V-07 Sign-in limit (Any (dedicated test account))

Run in: Chrome, Safari (iPhone 13).

1. Use a test account made for this case only.
2. Enter a wrong password five times, then the right password.
3. Wait 15 minutes and sign in with the right password.

Expected: The sixth try is refused with "Too many tries, wait 15 minutes". After 15 minutes the right password works. Run the two copies at least 15 minutes apart and not while others test from the same network: 30 failures from one internet address lock every account on it.

### V-08 Work queue order and For review (Staff)

Run in: Chrome, Edge, Firefox, Safari (iPhone 13), Chrome (Android, Poco F6).

1. Sign in as staff and open the queue.
2. Open For review and one request in it.

Expected: Requests a resident marked urgent come first, then higher urgency and longer waiting. In For review, category and urgency start at the model's prediction.

### V-09 Duplicate suggestions, link and unlink (Staff)

Run in: Chrome, Edge, Firefox.

1. Two residents submit VERIFICATION TEST reports of the same problem in similar words.
2. Open the newer one: under "An earlier report may be the same problem" tick Same problem and link it.
3. Remove the link, then link again for V-05.

Expected: The earlier report is suggested, the link saves and shows on both reports, and the link can be removed.

### V-10 Refer a concern to an agency (Staff)

Run in: Chrome, Edge, Firefox, Safari (iPhone 13), Chrome (Android, Poco F6).

1. Open a VERIFICATION TEST request that is Received, Being checked or with a handler.
2. Choose "Refer to another agency", pick an agency, add a note, confirm.
3. Open Referred requests. Take the referral back, then refer it again for V-06.

Expected: The request leaves the queue and is listed under Referred requests. Taking it back returns it to the queue.

### V-11 Approve a sign-up and record the check (Staff)

Run in: Chrome, Edge, Firefox.

1. Open Sign-ups and the account from V-01.
2. Try to approve without choosing how the resident was checked.
3. Choose one of "Valid ID, shown in person", "I know them personally", "Checked barangay records" and approve.

Expected: Approval needs a choice. With the email not yet confirmed, only "Valid ID, shown in person" allows approval. The resident can then sign in.

### V-12 Update status with a note (Staff)

Run in: Chrome, Edge, Firefox, Safari (iPhone 13), Chrome (Android, Poco F6).

1. Open a VERIFICATION TEST request: Mark in progress with a note, Mark resolved, then Close.

Expected: Each change saves and shows in the history; names and descriptions read as normal text; the resident sees the note.

### V-13 Administrator screens (Administrator)

Run in: Chrome, Edge, Firefox.

1. Accounts: search for a resident by part of the name.
2. Puroks and streets, and Agencies for referrals: open both; enter the contact details of each agency.
3. Site settings: save without changes. Audit log: find today's entries.

Expected: Search finds the account (names are encrypted, so the search runs in the application). Lists save. The audit log shows today's request.referred and attachment.uploaded entries.

### V-14 Sign-out, 8-hour session, private window (Any)

Run in: Chrome, Edge, Firefox, Safari (iPhone 13), Chrome (Android, Poco F6).

1. Desktop: sign in, open DevTools > Application (Storage in Firefox) > Cookies and read the session cookie.
2. Sign out, press Back, then paste a signed-in address.
3. Repeat sign-in and sign-out in a private window.

Expected: Desktop: the cookie is HttpOnly, Secure and SameSite=Lax and expires 8 hours after sign-in. After sign-out Back and the pasted address show no data. The private window behaves the same.

Database check for V-03 (Chrome run), from the laptop:

```bash
ssh gabai "docker exec gabai-db psql -U gabai -d gabai -At -c \"select left(description, 10) from requests where reference_number = 'GAB-2026-NNNNN'\""
```

Expected output: `gabai:enc:`.

## B. Performance after encryption

**Done on 23 October 2026. Run on the project laptop, in the morning when the site is quiet. It asks for the two test accounts and tells you what to do at each step.**

- `cd ~/Desktop/Personal/GABAI`
- `bash tests/load/run_final_load.sh`

## C. Restore drill

**Done on 23 October 2026. Run on the project laptop, with Docker Desktop running and nobody using the site. It tells you which two files to download from Google Drive and waits for you.**

- `cd ~/Desktop/Personal/GABAI`
- `bash tests/restore/run_drill.sh`
