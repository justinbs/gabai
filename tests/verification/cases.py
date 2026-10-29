"""Workflows re-run on the final build (paper Table 20A). Shared by the README and the printable sheet."""

ENVIRONMENTS = [
    ("Chrome", "Windows laptop"), ("Edge", "Windows laptop"), ("Firefox", "Windows laptop"),
    ("Safari (macOS)", "borrowed Mac, 24 October 2026"), ("Safari (iPhone 13)", "iPhone 13 with Safari"),
    ("Chrome (Android, Poco F6)", "Poco F6 with Chrome"),
]
DESKTOP = ["Chrome", "Edge", "Firefox"]
PHONES = ["Safari (iPhone 13)", "Chrome (Android, Poco F6)"]

# id, title, role, where to run, steps, expected
CASES = [
    ("V-01", "Sign-up with purok or street and terms acceptance", "Resident", DESKTOP + PHONES,
     ["Open https://gabai.help and choose Register.",
      "Enter a name, a new email (for example yourname+v01chrome@gmail.com), a purok or street and a password.",
      "Try to submit with the Terms of Use and Privacy Notice box unticked.",
      "Tick the box and submit. Open the Terms link."],
     "The form will not submit until the box is ticked. The account is created and the screen says to confirm "
     "the email and wait for approval. The Terms page shows the version of 16 October 2026."),
    ("V-02", "Email confirmation, sign-in and password reset", "Resident", DESKTOP + PHONES,
     ["Open the confirmation link from the V-01 email in the same browser.",
      "Sign in: the waiting screen shows until staff approve the account (V-11), then the resident home.",
      "Sign out, choose Forgot password, open the reset link, set a new password.",
      "Sign in with the old password, then with the new one."],
     "The email is confirmed and the token after # disappears from the address bar. The old password is "
     "refused and the new one works."),
    ("V-03", "Submit a request with a place", "Resident", DESKTOP + PHONES,
     ["Open Report a concern. Type a description that starts with VERIFICATION TEST.",
      "Under \"Where is the problem? · Saan po ang problema?\" choose a purok or street.",
      "Submit, then open My requests and the new request."],
     "A reference number GAB-YYYY-NNNNN shows at once. The request, its place and its description read as "
     "normal text. Chrome run only: the database check in the README shows the stored description starts "
     "with gabai:enc:."),
    ("V-04", "Attach a photo and a 2.8 MB PDF, then download them", "Resident", DESKTOP + PHONES,
     ["On a new VERIFICATION TEST request, attach a phone photo and the 2.8 MB PDF used for CB-24.",
      "Submit. Open the request and download both files.",
      "Desktop only: in PowerShell run Get-FileHash on the original PDF and on the downloaded PDF."],
     "Both files upload and open. Desktop: the two PDF SHA-256 values are equal. (Photos are reduced in the "
     "browser before upload, so only the PDF can match exactly.) Note the result of the PDF on each phone."),
    ("V-05", "Follow a request; urgent once; notes from a linked report", "Resident", DESKTOP + PHONES,
     ["On an open VERIFICATION TEST request press \"This is urgent · Urgent po ito\" and give a reason.",
      "Check whether the button can be pressed again.",
      "After staff link the request to a main report and add a note (V-09, V-12), open it again."],
     "The urgent flag is accepted once and the button does not come back. The linked request shows "
     "\"Others reported the same problem\", the main report's status and the staff note. Times are Philippine time."),
    ("V-06", "A referred request shows the agency", "Resident", DESKTOP + PHONES,
     ["After staff refer a VERIFICATION TEST request (V-10), open it as the resident."],
     "The status reads Referred, with the agency's name and the contact details the administrator entered (V-13)."),
    ("V-07", "Sign-in limit", "Any (dedicated test account)", ["Chrome", "Safari (iPhone 13)"],
     ["Use a test account made for this case only.",
      "Enter a wrong password five times, then the right password.",
      "Wait 15 minutes and sign in with the right password."],
     "The sixth try is refused with \"Too many tries, wait 15 minutes\". After 15 minutes the right password "
     "works. Run the two copies at least 15 minutes apart and not while others test from the same network: "
     "30 failures from one internet address lock every account on it."),
    ("V-08", "Work queue order and For review", "Staff", DESKTOP + PHONES,
     ["Sign in as staff and open the queue.", "Open For review and one request in it."],
     "Requests a resident marked urgent come first, then higher urgency and longer waiting. In For review, "
     "category and urgency start at the model's prediction."),
    ("V-09", "Duplicate suggestions, link and unlink", "Staff", DESKTOP,
     ["Two residents submit VERIFICATION TEST reports of the same problem in similar words.",
      "Open the newer one: under \"An earlier report may be the same problem\" tick Same problem and link it.",
      "Remove the link, then link again for V-05."],
     "The earlier report is suggested, the link saves and shows on both reports, and the link can be removed."),
    ("V-10", "Refer a concern to an agency", "Staff", DESKTOP + PHONES,
     ["Open a VERIFICATION TEST request that is Received, Being checked or with a handler.",
      "Choose \"Refer to another agency\", pick an agency, add a note, confirm.",
      "Open Referred requests. Take the referral back, then refer it again for V-06."],
     "The request leaves the queue and is listed under Referred requests. Taking it back returns it to the queue."),
    ("V-11", "Approve a sign-up and record the check", "Staff", DESKTOP,
     ["Open Sign-ups and the account from V-01.",
      "Try to approve without choosing how the resident was checked.",
      "Choose one of \"Valid ID, shown in person\", \"I know them personally\", \"Checked barangay records\" and approve."],
     "Approval needs a choice. With the email not yet confirmed, only \"Valid ID, shown in person\" allows approval. "
     "The resident can then sign in."),
    ("V-12", "Update status with a note", "Staff", DESKTOP + PHONES,
     ["Open a VERIFICATION TEST request: Mark in progress with a note, Mark resolved, then Close."],
     "Each change saves and shows in the history; names and descriptions read as normal text; the resident sees the note."),
    ("V-13", "Administrator screens", "Administrator", DESKTOP,
     ["Accounts: search for a resident by part of the name.",
      "Puroks and streets, and Agencies for referrals: open both; enter the contact details of each agency.",
      "Site settings: save without changes. Audit log: find today's entries."],
     "Search finds the account (names are encrypted, so the search runs in the application). Lists save. The "
     "audit log shows today's request.referred and attachment.uploaded entries."),
    ("V-14", "Sign-out, 8-hour session, private window", "Any", DESKTOP + PHONES,
     ["Desktop: sign in, open DevTools > Application (Storage in Firefox) > Cookies and read the session cookie.",
      "Sign out, press Back, then paste a signed-in address.",
      "Repeat sign-in and sign-out in a private window."],
     "Desktop: the cookie is HttpOnly, Secure and SameSite=Lax and expires 8 hours after sign-in. After sign-out "
     "Back and the pasted address show no data. The private window behaves the same."),
]
