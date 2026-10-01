// Terms of Use and Privacy Notice shown at sign-up.
// If the text changes, update TERMS_VERSION here and in backend/app/terms.py.

export const TERMS_VERSION = "2026-10-01";
export const TERMS_EFFECTIVE = "1 October 2026";

export type Section = { heading: string; paragraphs?: string[]; items?: string[] };
export type LegalDoc = { title: string; tagalog: string; summary: string; sections: Section[] };

type Site = { barangay_name: string; place: string; address: string | null; hotline: string | null };

const DEVELOPERS =
  "Jean Clarisse D. Dalu, Bart Daniel P. Dayao and Justin Brylle G. Salazar, BS Information Technology students of Mapúa University";

function office(site: Site): string {
  const where = site.address ? ` at ${site.address}` : "";
  const call = site.hotline ? `, or call ${site.hotline}` : "";
  return `Visit the ${site.barangay_name} office${where}${call}.`;
}

export function termsOfUse(site: Site): LegalDoc {
  return {
    title: "Terms of Use",
    tagalog: "Mga Tuntunin ng Paggamit",
    summary:
      "Use GABAI to send the barangay your concerns and follow what happens to them. Tell the truth, keep your password to yourself, and call for help directly in an emergency. · Gamitin ang GABAI para ipaabot sa barangay ang inyong mga hinaing at subaybayan ang mga ito. Magsabi ng totoo, huwag ibigay ang password, at tumawag agad kung may emergency.",
    sections: [
      {
        heading: "What GABAI is",
        paragraphs: [
          `GABAI lets residents of ${site.barangay_name}, ${site.place}, send requests and complaints to the barangay and follow their progress. Each request is sorted automatically by category and urgency and sent to the staff member who handles that kind of concern. When the system isn't sure, a staff member sorts it instead.`,
          `GABAI was developed by ${DEVELOPERS}, as part of their thesis study, working with the barangay. It is offered as is, and it may sometimes be unavailable.`,
        ],
      },
      {
        heading: "Not for emergencies",
        paragraphs: [
          "Requests are read during office hours, not watched around the clock. For a fire, a crime in progress, a medical emergency or anything else that can't wait, call 911 or go to the barangay hall right away.",
        ],
      },
      {
        heading: "Who can use it",
        paragraphs: [
          "Residents of the barangay can sign up. Staff check your purok or street before your account can be used. Staff and administrator accounts are made by an administrator.",
        ],
      },
      {
        heading: "What you agree to",
        items: [
          "Give your real name and your own email address.",
          "Describe your concern truthfully. False reports take time away from real ones.",
          "Share other people's personal details only when the concern needs them.",
          "Don't send threats, insults or content meant to harass anyone.",
          "Attach only photos and files you took yourself or have the right to share.",
          "Keep your password to yourself. You're responsible for what's done with your account.",
        ],
      },
      {
        heading: "How your requests are handled",
        paragraphs: [
          "The barangay decides what action to take on each request and when. Sending a request through GABAI doesn't guarantee a particular result or time. You can still raise any concern in person at the barangay office.",
        ],
      },
      {
        heading: "Your account",
        paragraphs: [
          `The barangay may deactivate an account that is misused. Accounts are deactivated, never deleted, so the record of what was done stays whole. To close your account or ask about it: ${office(site)}`,
        ],
      },
      {
        heading: "Content and ownership",
        paragraphs: [
          `What you write and attach stays yours. By sending it, you let the barangay use it to handle your request. The barangay's name and seal belong to ${site.barangay_name}.`,
          "The layout and default colours are based on the GOV.UK Design System, used under the MIT License. The masthead typeface is Cinzel, used under the SIL Open Font License. GABAI uses no other outside images or artwork.",
        ],
      },
      {
        heading: "Changes to these terms",
        paragraphs: [
          "If these terms change, you'll be asked to read and accept them again the next time you use GABAI. The law of the Philippines applies to these terms.",
        ],
      },
    ],
  };
}

export function privacyNotice(site: Site): LegalDoc {
  return {
    title: "Privacy Notice",
    tagalog: "Abiso sa Pagkapribado",
    summary:
      "We collect only what's needed to handle your request, show it only to barangay staff who need it, and keep it for as long as the barangay decides. You have rights under the Data Privacy Act of 2012. · Kinokolekta lang namin ang kailangan para maasikaso ang inyong kahilingan, ipinapakita lang ito sa mga staff ng barangay na nangangailangan nito, at itinatago ito hangga't itinakda ng barangay. May karapatan kayo sa ilalim ng Data Privacy Act of 2012.",
    sections: [
      {
        heading: "Who is responsible for your data",
        paragraphs: [
          `${site.barangay_name}, ${site.place}, is responsible for the personal data in GABAI, as the personal information controller under the Data Privacy Act of 2012 (Republic Act No. 10173).`,
          `GABAI was developed, and is maintained during the study, by ${DEVELOPERS}. They handle the data only to run and fix the system, for the barangay.`,
          `For any question about your data: ${office(site)}`,
        ],
      },
      {
        heading: "What we collect",
        items: [
          "Your name, email address, and purok or street.",
          "Your password, stored only in a scrambled form that can't be turned back into the password.",
          "The requests you send: what you write, the photos or files you attach, and when you sent them.",
          "What happens to each request: its status, the staff member handling it, and staff notes to you.",
          "Messages the system sends you about your requests.",
          "For actions by staff and administrators, and for accepting these terms: who did it, when, and the internet address it came from.",
        ],
      },
      {
        heading: "Why we collect it",
        items: [
          "To confirm you live in the barangay before your account is used.",
          "To send your request to the right staff member and tell you what happens to it.",
          "To keep a record of who did what, so the handling of every request can be checked.",
          "To keep the system secure and working.",
        ],
      },
      {
        heading: "Automatic sorting",
        paragraphs: [
          "A computer model reads the text of your request and suggests its category and urgency. It only sorts requests. It doesn't decide what the barangay does about them. When the model isn't confident, a staff member sorts the request instead, and staff can change the model's choice at any time. Your requests aren't used to train the model.",
        ],
      },
      {
        heading: "Who can see it",
        items: [
          "You can see your own account and requests.",
          "Staff see the requests in the categories they handle, requests assigned to them, and requests waiting to be sorted.",
          "Staff and administrators see the purok or street you gave, to check you live in the barangay.",
          "Administrators can see every request and account, and the record of actions.",
        ],
        paragraphs: [
          "We don't sell or share your data with anyone else, except these services that run the system for the barangay: DigitalOcean, which hosts the server in Singapore; Resend, a company in the United States, which sends our emails; and Google Drive, where daily backup copies are kept in an account used only for GABAI. These services may store data outside the Philippines. We would also disclose data when the law requires it.",
        ],
      },
      {
        heading: "How long we keep it",
        paragraphs: [
          "The barangay decides how long personal data is kept. Once it sets those periods, the system removes the description, notes and attachments of requests resolved or closed longer ago than that, keeping only the reference number, category and dates for the barangay's reports. It also removes the name, email and purok or street of accounts deactivated or turned down longer ago than that, and the internet addresses in the record of actions. Until the barangay sets the periods, nothing is removed automatically. Backup copies are kept for 14 days.",
        ],
      },
      {
        heading: "How we protect it",
        items: [
          "Every connection to GABAI is encrypted.",
          "Each person sees only what their role needs.",
          "The record of actions can't be changed or deleted, even by an administrator. Only the internet addresses in it are cleared after the retention period.",
          "Passwords are never stored as written.",
          "Backups are made every night.",
        ],
      },
      {
        heading: "Cookies",
        paragraphs: [
          "GABAI uses one cookie, which keeps you signed in. There are no advertising or tracking cookies.",
        ],
      },
      {
        heading: "Your rights",
        paragraphs: [
          `Under the Data Privacy Act you have the right to be informed about how your data is used, to see the data held about you, to have it corrected, to object to its use, to have it removed or blocked, to get a copy of it, and to claim damages if it's misused. To use any of these rights: ${office(site)} You can also file a complaint with the National Privacy Commission.`,
        ],
      },
      {
        heading: "Changes to this notice",
        paragraphs: [
          `This notice took effect on ${TERMS_EFFECTIVE}. If it changes, you'll be asked to read and accept it again the next time you use GABAI.`,
        ],
      },
    ],
  };
}
