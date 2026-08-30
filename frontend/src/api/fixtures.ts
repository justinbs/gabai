import type {
  Category,
  Notification,
  Role,
  ServiceRequest,
  User,
  UserSummary,
} from "./types";

// Sample data for the prototype. Typed against the generated schema, so a change
// to openapi.yaml that these no longer satisfy fails the build.
//
// Names are invented. Do not use real barangay officials or interview subjects
// here — this data gets screenshotted into the paper and shown to evaluation
// respondents, and consent to be interviewed is not consent to appear as a user
// account.
//
// Category names are PROVISIONAL — the group has not locked the list yet. They
// live only here; nothing else in the app hardcodes a category.

export const categories: Category[] = [
  {
    id: 1,
    slug: "road_infrastructure",
    name: "Road & Infrastructure",
    description: "Potholes, damaged roads, bridges, streetlights, drainage structures",
    is_active: true,
  },
  {
    id: 2,
    slug: "public_health_sanitation",
    name: "Public Health & Sanitation",
    description: "Garbage collection, stagnant water, pests, health center concerns",
    is_active: true,
  },
  {
    id: 3,
    slug: "public_safety",
    name: "Public Safety & Peace and Order",
    description: "Suspicious activity, hazards, curfew, stray animals",
    is_active: true,
  },
  {
    id: 4,
    slug: "utilities",
    name: "Utilities",
    description: "Water interruption, power, flooding, drainage blockage",
    is_active: true,
  },
  {
    id: 5,
    slug: "social_welfare",
    name: "Social Welfare & Assistance",
    description: "Ayuda, senior and PWD concerns, indigency, financial assistance",
    is_active: true,
  },
  {
    id: 6,
    slug: "neighbor_dispute",
    name: "Neighbor Dispute & Nuisance",
    description: "Noise, boundary, tenant, and other interpersonal concerns",
    is_active: true,
  },
  {
    id: 7,
    slug: "other",
    name: "Other / General Inquiry",
    description: "Anything that does not fit the categories above",
    is_active: true,
  },
];

const byId = (id: number) => categories.find((c) => c.id === id)!;

export const users: Record<Role, User> = {
  citizen: {
    id: "8f1c1d2e-0000-4000-8000-000000000001",
    email: "maria.santos@example.com",
    full_name: "Maria Santos",
    role: "citizen",
    is_active: true,
    created_at: "2026-07-02T01:20:00Z",
  },
  staff: {
    id: "8f1c1d2e-0000-4000-8000-000000000002",
    email: "ramon.delgado@example.com",
    full_name: "Ramon Delgado",
    role: "staff",
    is_active: true,
    created_at: "2026-06-15T00:00:00Z",
  },
  admin: {
    id: "8f1c1d2e-0000-4000-8000-000000000003",
    email: "teresa.ocampo@example.com",
    full_name: "Teresa Ocampo",
    role: "admin",
    is_active: true,
    created_at: "2026-06-15T00:00:00Z",
  },
};

// A second handler, so reassignment is demonstrable. Correcting a category
// re-runs routing and can move a request to a different officer — with only one
// staff user that consequence is invisible.
export const otherStaff: User = {
  id: "8f1c1d2e-0000-4000-8000-000000000004",
  email: "divina.bautista@example.com",
  full_name: "Divina Bautista",
  role: "staff",
  is_active: true,
  created_at: "2026-06-15T00:00:00Z",
};

const summary = (u: User): UserSummary => ({
  id: u.id,
  full_name: u.full_name,
  role: u.role,
});

const staff = summary(users.staff);
const staffB = summary(otherStaff);
const citizen = summary(users.citizen);

// Who handles what. Mirrors routing_rules; the admin routing screen edits this.
export const routing: Record<number, UserSummary> = {
  1: staff, // Road & Infrastructure
  2: staffB, // Public Health & Sanitation
  3: staff, // Public Safety
  4: staffB, // Utilities
  5: staffB, // Social Welfare
  6: staff, // Neighbor Dispute
  7: staff, // Other
};

// Placeholder. The real checkpoint name is blocked on the model-choice gate, and
// hardcoding one here would put an undecided choice into a screenshot.
const MODEL_VERSION = "classifier-v1";

// Hours ago, as an ISO string. Keeps the queue's "age" column plausible whenever
// the prototype is opened.
const ago = (hours: number) =>
  new Date(Date.now() - hours * 3_600_000).toISOString();

type Seed = {
  id: number;
  ref: string;
  text: string;
  categoryId: number | null;
  urgency: ServiceRequest["predicted_urgency"];
  catConf: number | null;
  urgConf: number | null;
  status: ServiceRequest["status"];
  hours: number;
  assigned: boolean;
  finalCategoryId?: number;
  finalUrgency?: NonNullable<ServiceRequest["final_urgency"]>;
};

// Written to read like real barangay submissions: code-switched, unpunctuated,
// misspelled, occasionally shouting. Clean text would make the classifier look
// better than it is.
//
// Confidences obey the contract's own routing rule — anything whose lower score
// falls under 0.70 is `under_review`, never `routed`. These numbers end up in
// screenshots, so a routed request below threshold would contradict the paper.
const seeds: Seed[] = [
  {
    id: 42, ref: "GAB-2026-00042",
    text: "may malaking butas sa kalsada sa may tabi ng barangay hall delikado na lalo pag gabi wala pang ilaw",
    categoryId: 1, urgency: "high", catConf: 0.94, urgConf: 0.88,
    status: "routed", hours: 3, assigned: true,
  },
  {
    id: 41, ref: "GAB-2026-00041",
    text: "PAKI AYOS NAMAN PO YUNG STREETLIGHT SA CORNER MADILIM SOBRA TAKOT KAMI DUMAAN PAG GABI",
    categoryId: 1, urgency: "high", catConf: 0.89, urgConf: 0.91,
    status: "in_progress", hours: 26, assigned: true,
  },
  {
    id: 40, ref: "GAB-2026-00040",
    text: "wala kaming tubig since kahapon po sa buong purok 5 ano po ba nangyari dito",
    categoryId: 4, urgency: "high", catConf: 0.92, urgConf: 0.84,
    status: "routed", hours: 5, assigned: true,
  },
  {
    id: 39, ref: "GAB-2026-00039",
    text: "aso ng kapitbahay palaboy lagi at muntik na makagat yung anak ko kanina sa kalye",
    categoryId: 3, urgency: "high", catConf: 0.81, urgConf: 0.87,
    status: "routed", hours: 9, assigned: true,
  },
  {
    id: 38, ref: "GAB-2026-00038",
    text: "yung poste ng kuryente sa harap ng bahay namin nakahilig na parang matutumba na po",
    categoryId: 4, urgency: "high", catConf: 0.73, urgConf: 0.9,
    status: "in_progress", hours: 50, assigned: true,
  },
  {
    id: 37, ref: "GAB-2026-00037",
    text: "hindi na po nakokolekta yung basura namin sa purok 3 mga 2 weeks na amoy na amoy na",
    categoryId: 2, urgency: "medium", catConf: 0.95, urgConf: 0.79,
    status: "routed", hours: 30, assigned: true,
  },
  {
    id: 36, ref: "GAB-2026-00036",
    text: "baradong kanal sa likod ng school tuwing umuulan binabaha agad hanggang tuhod",
    categoryId: 4, urgency: "medium", catConf: 0.72, urgConf: 0.77,
    status: "routed", hours: 54, assigned: true,
  },
  {
    id: 35, ref: "GAB-2026-00035",
    text: "yung kapitbahay po namin sobrang lakas ng videoke gabi gabi hanggang alas dos ng madaling araw",
    categoryId: 6, urgency: "medium", catConf: 0.86, urgConf: 0.72,
    status: "in_progress", hours: 74, assigned: true,
  },
  {
    id: 34, ref: "GAB-2026-00034",
    text: "may mga tambay po sa may basketball court tuwing gabi naninigarilyo at umiinom nakakatakot dumaan",
    categoryId: 3, urgency: "medium", catConf: 0.78, urgConf: 0.71,
    status: "routed", hours: 80, assigned: true,
  },
  {
    id: 33, ref: "GAB-2026-00033",
    text: "nasira po yung kubeta sa health center di magamit ng mga nagpapacheck up",
    categoryId: 2, urgency: "medium", catConf: 0.83, urgConf: 0.7,
    status: "resolved", hours: 120, assigned: true,
  },
  {
    id: 32, ref: "GAB-2026-00032",
    text: "sobrang lubak lubak na po yung daan papasok sa purok 7 hirap dumaan ang tricycle",
    categoryId: 1, urgency: "medium", catConf: 0.91, urgConf: 0.74,
    status: "closed", hours: 200, assigned: true,
  },
  {
    id: 31, ref: "GAB-2026-00031",
    text: "pwede po bang magtanong kung kelan yung next na ayuda para sa senior citizen salamat po",
    categoryId: 5, urgency: "low", catConf: 0.88, urgConf: 0.81,
    status: "resolved", hours: 150, assigned: true,
  },
  // Model confidently wrong, corrected by staff. Predicted Utilities; a human
  // reclassified it as Road & Infrastructure. Exercises the predicted-vs-final
  // split, which is the correction evidence Chapter 4 rests on.
  {
    id: 27, ref: "GAB-2026-00027",
    text: "tuwing umuulan po hindi humuhupa yung tubig sa kanto namin kasi barado yung daluyan sa ilalim ng kalsada",
    categoryId: 4, urgency: "medium", catConf: 0.76, urgConf: 0.8,
    status: "routed", hours: 60, assigned: true,
    finalCategoryId: 1, finalUrgency: "medium",
  },
  // --- below threshold, sitting in the manual review queue -----------------
  {
    id: 30, ref: "GAB-2026-00030",
    text: "may nag tapon ng basura sa lote namin gabi gabi hindi namin alam kung sino sana matulungan nyo kami",
    categoryId: 2, urgency: "medium", catConf: 0.44, urgConf: 0.58,
    status: "under_review", hours: 12, assigned: false,
  },
  {
    id: 29, ref: "GAB-2026-00029",
    text: "po pwede po ba magpa barangay clearance online o kailangan pumunta talaga",
    categoryId: 7, urgency: "low", catConf: 0.52, urgConf: 0.63,
    status: "under_review", hours: 20, assigned: false,
  },
  {
    id: 28, ref: "GAB-2026-00028",
    text: "matagal na po yung usapin namin ng kapitbahay tungkol sa hangganan ng lote pero wala pa ring aksyon",
    categoryId: 6, urgency: "medium", catConf: 0.49, urgConf: 0.41,
    status: "under_review", hours: 44, assigned: false,
  },
  // Near miss — 0.69 is the case that justifies tuning the threshold from data
  // rather than picking 0.70 by feel.
  {
    id: 26, ref: "GAB-2026-00026",
    text: "may sirang bahagi ng bakod sa may plaza matulis yung bakal baka may masugatan na bata",
    categoryId: 1, urgency: "medium", catConf: 0.69, urgConf: 0.71,
    status: "under_review", hours: 16, assigned: false,
  },
  // --- just submitted, classifier has not run yet --------------------------
  {
    id: 43, ref: "GAB-2026-00043",
    text: "ask ko lang po sino po ba contact person for indigency certificate salamat",
    categoryId: null, urgency: null, catConf: null, urgConf: null,
    status: "submitted", hours: 0.2, assigned: false,
  },
];

const historyFor = (s: Seed): ServiceRequest["status_history"] => {
  const entries: ServiceRequest["status_history"] = [
    {
      id: s.id * 10,
      from_status: null,
      to_status: "submitted",
      actor: citizen,
      note: null,
      created_at: ago(s.hours),
    },
  ];
  if (s.status === "submitted") return entries;

  if (s.status === "under_review") {
    entries.push({
      id: s.id * 10 + 1,
      from_status: "submitted",
      to_status: "under_review",
      actor: null,
      note: "Confidence below threshold. Sent for manual review.",
      created_at: ago(s.hours - 0.05),
    });
    return entries;
  }

  entries.push({
    id: s.id * 10 + 1,
    from_status: "submitted",
    to_status: "classified",
    actor: null,
    note: null,
    created_at: ago(s.hours - 0.05),
  });
  entries.push({
    id: s.id * 10 + 2,
    from_status: "classified",
    to_status: "routed",
    actor: null,
    note: `Routed to ${routing[s.categoryId!].full_name}.`,
    created_at: ago(s.hours - 0.06),
  });
  if (s.status === "routed") return entries;

  entries.push({
    id: s.id * 10 + 3,
    from_status: "routed",
    to_status: "in_progress",
    actor: staff,
    note: "Nakita na po namin, aaksyunan namin ito.",
    created_at: ago(s.hours * 0.6),
  });
  if (s.status === "in_progress") return entries;

  entries.push({
    id: s.id * 10 + 4,
    from_status: "in_progress",
    to_status: "resolved",
    actor: staff,
    note: "Naayos na po. Salamat sa pag-report.",
    created_at: ago(s.hours * 0.25),
  });
  if (s.status === "resolved") return entries;

  entries.push({
    id: s.id * 10 + 5,
    from_status: "resolved",
    to_status: "closed",
    actor: staff,
    note: null,
    created_at: ago(s.hours * 0.1),
  });
  return entries;
};

const toRequest = (s: Seed): ServiceRequest => {
  const predicted = s.categoryId === null ? null : byId(s.categoryId);
  const final = s.finalCategoryId ? byId(s.finalCategoryId) : null;
  const finalUrgency = s.finalUrgency ?? null;
  const resolved = s.status === "resolved" || s.status === "closed";

  return {
    id: s.id,
    reference_number: s.ref,
    citizen,
    description: s.text,
    predicted_category: predicted,
    predicted_urgency: s.urgency,
    category_confidence: s.catConf,
    urgency_confidence: s.urgConf,
    final_category: final,
    final_urgency: finalUrgency,
    // Effective value, exactly as the API computes it: human label if one exists,
    // otherwise the prediction.
    category: final ?? predicted,
    urgency: finalUrgency ?? s.urgency,
    status: s.status,
    assigned_staff:
      s.assigned && (final ?? predicted)
        ? routing[(final ?? predicted)!.id]
        : null,
    model_version: s.catConf === null ? null : MODEL_VERSION,
    classified_at: s.catConf === null ? null : ago(s.hours - 0.05),
    created_at: ago(s.hours),
    updated_at: ago(s.hours * 0.5),
    resolved_at: resolved ? ago(s.hours * 0.25) : null,
    attachments:
      s.id === 42
        ? [
            {
              id: 1,
              filename: "butas-sa-kalsada.jpg",
              mime_type: "image/jpeg",
              size_bytes: 842_113,
              uploaded_at: ago(s.hours),
            },
          ]
        : [],
    status_history: historyFor(s),
  };
};

export const requests: ServiceRequest[] = seeds.map(toRequest);

// The API scopes notifications server-side, so `Notification` carries no owner.
// The prototype has to scope them somewhere, so ownership is tracked here.
export type OwnedNotification = { userId: string; notification: Notification };

export const notifications: OwnedNotification[] = [
  {
    userId: users.citizen.id,
    notification: {
      id: 1,
      request_id: 42,
      reference_number: "GAB-2026-00042",
      message: "Your request has been routed to a barangay officer.",
      is_read: false,
      created_at: ago(3),
    },
  },
  {
    userId: users.citizen.id,
    notification: {
      id: 2,
      request_id: 41,
      reference_number: "GAB-2026-00041",
      message: "Your request is now in progress.",
      is_read: false,
      created_at: ago(20),
    },
  },
  {
    userId: users.citizen.id,
    notification: {
      id: 3,
      request_id: 33,
      reference_number: "GAB-2026-00033",
      message: "Your request has been resolved.",
      is_read: true,
      created_at: ago(30),
    },
  },
  {
    userId: users.staff.id,
    notification: {
      id: 4,
      request_id: 26,
      reference_number: "GAB-2026-00026",
      message: "A request needs manual classification.",
      is_read: false,
      created_at: ago(16),
    },
  },
];
