import { NavLink, Outlet } from "react-router-dom";

import { Button, FOCUS_LINK } from "./ui";
import { useSession } from "../session-context";
import { NotificationBell } from "./NotificationBell";

// Nav is role-scoped, but that is presentation only. The real system enforces
// every rule server-side, hiding a link is not access control.
const LINKS = {
  // Just the one. Reporting is a green button on the list page, and repeating
  // it here put the same words twice on one screen.
  citizen: [{ to: "/requests", label: "My requests" }],
  staff: [
    { to: "/queue", label: "Queue" },
    { to: "/review", label: "For review" },
  ],
  admin: [
    { to: "/queue", label: "Queue" },
    { to: "/review", label: "For review" },
    { to: "/admin/accounts", label: "Accounts" },
    { to: "/admin/routing", label: "Routing" },
    { to: "/admin/audit", label: "Audit log" },
  ],
};

export function AppShell() {
  const { user, signOut } = useSession();
  if (!user) return null;

  return (
    <div className="min-h-screen bg-white">
      <a
        href="#main"
        className={`sr-only focus:not-sr-only focus:absolute focus:m-2 focus:bg-focus focus:px-4 focus:py-2 focus:font-bold focus:text-ink ${FOCUS_LINK}`}
      >
        Skip to main content
      </a>

      {/* Black, and it names the barangay. A system for one place should say
          which place. */}
      <header className="bg-ink">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
          <img
            src="/barangay-logo.jpg"
            alt="Barangay V logo"
            className="h-10 w-10 object-contain"
          />
          <span className="text-xl font-bold tracking-tight text-white">
            GABAI
          </span>
          <span className="text-[15px] text-white/80">
            Barangay V (Singko), Amaya, Tanza, Cavite
          </span>
          <span className="ml-auto text-[15px] text-white/80">
            {user.full_name}
          </span>
        </div>
      </header>

      <div className="h-2.5 bg-brand" />

      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <nav aria-label="Main">
          <ul className="flex flex-wrap gap-6">
            {LINKS[user.role].map((link) => (
              <li key={link.to}>
                <NavLink
                  to={link.to}
                  className={({ isActive }) =>
                    `${FOCUS_LINK} ${
                      isActive ? "font-bold" : "text-link underline"
                    }`
                  }
                >
                  {link.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <NotificationBell />
        <Button variant="secondary" onClick={signOut}>
          Sign out
        </Button>
      </div>

      <main id="main" className="mx-auto max-w-5xl px-4 pb-16">
        <Outlet />
      </main>
    </div>
  );
}
