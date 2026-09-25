import { NavLink, Outlet } from "react-router-dom";

import { FOCUS_LINK } from "./ui";
import { useSession } from "../session-context";
import { NotificationBell } from "./NotificationBell";
import { Masthead, SiteFooter, SkipLink, TopBar } from "./SiteChrome";

// Nav is role-scoped, but that is presentation only. The real system enforces
// every rule server-side, hiding a link is not access control.
const LINKS = {
  // Just the one. Reporting is a green button on the list page, and repeating
  // it here put the same words twice on one screen.
  citizen: [{ to: "/requests", label: "My requests" }],
  staff: [
    { to: "/queue", label: "Queue" },
    { to: "/review", label: "For review" },
    { to: "/sign-ups", label: "Sign-ups" },
  ],
  admin: [
    { to: "/queue", label: "Queue" },
    { to: "/review", label: "For review" },
    { to: "/sign-ups", label: "Sign-ups" },
    { to: "/admin/accounts", label: "Accounts" },
    { to: "/admin/routing", label: "Routing" },
    { to: "/admin/audit", label: "Audit log" },
  ],
};

export function AppShell() {
  const { user, signOut } = useSession();
  if (!user) return null;
  // Nothing else works while waiting for approval or on a temporary password,
  // so don't offer it.
  const pending = user.approval_status !== "approved" || user.must_change_password;

  return (
    <div className="flex min-h-screen flex-col bg-white">
      <SkipLink />

      <header>
        <TopBar user={user} onSignOut={signOut} />
        <Masthead />
      </header>

      <div className="h-2.5 bg-brand" />

      {!pending && (
        <div className="border-b border-rule">
          <div className="mx-auto flex w-full max-w-[1190px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
            <nav aria-label="Main">
              <ul className="flex flex-wrap gap-6">
                {LINKS[user.role].map((link) => (
                  <li key={link.to}>
                    <NavLink
                      to={link.to}
                      className={({ isActive }) =>
                        `${FOCUS_LINK} ${isActive ? "font-bold" : "text-link underline"}`
                      }
                    >
                      {link.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </nav>
            <div className="ml-auto">
              <NotificationBell />
            </div>
          </div>
        </div>
      )}

      <main id="main" className="mx-auto w-full max-w-[1190px] flex-1 px-4 pt-6">
        <Outlet />
      </main>

      <SiteFooter />
    </div>
  );
}
