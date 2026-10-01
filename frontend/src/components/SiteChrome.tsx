import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useSite } from "../site-context";
import type { User } from "../api/types";
import { FOCUS_LINK } from "./ui";

// Layout follows DICT's government website template: dark top bar and a
// masthead with the seal and the office's name. Adapted, not copied. No Republic Seal (its use is restricted and this
// isn't an official government site), no search (nothing public to search) and
// no banner slideshow (heavy on data, and carousels are hard to use).

const TOP_BAR = "bg-[#222222] text-white";
const WIDTH = "mx-auto w-full max-w-[1190px] px-4";

export function SkipLink() {
  return (
    <a
      href="#main"
      className={`sr-only focus:not-sr-only focus:absolute focus:m-2 focus:bg-focus focus:px-4 focus:py-2 focus:font-bold focus:text-ink ${FOCUS_LINK}`}
    >
      Skip to main content
    </a>
  );
}

export function TopBar({
  user,
  onSignOut,
}: {
  user?: User;
  onSignOut?: () => void;
}) {
  return (
    <div className={TOP_BAR}>
      <div
        className={`${WIDTH} flex min-h-[45px] flex-wrap items-center gap-x-5 gap-y-1 py-2 text-[15px]`}
      >
        <Link to="/" className={`font-bold tracking-wide text-white ${FOCUS_LINK}`}>
          GABAI
        </Link>
        {user && (
          <>
            <span className="ml-auto hidden text-white/80 sm:inline">{user.full_name}</span>
            <Link
              to="/account"
              className={`ml-auto text-white underline sm:ml-0 ${FOCUS_LINK}`}
            >
              Your account
            </Link>
            <button
              type="button"
              onClick={onSignOut}
              className={`text-white underline ${FOCUS_LINK}`}
            >
              Sign out
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export function Masthead() {
  const { site, logoUrl } = useSite();
  return (
    <div className="bg-white">
      <div className={`${WIDTH} flex items-center gap-4 py-4 sm:py-5`}>
        <img
          src={logoUrl}
          alt={`${site.barangay_name} logo`}
          className="h-16 w-16 shrink-0 object-contain sm:h-[100px] sm:w-[100px]"
        />
        <div className="font-masthead text-[#222222]">
          <p className="text-[13px] tracking-wide sm:text-[16px]">Republika ng Pilipinas</p>
          <div className="my-1 h-px bg-[#222222]" />
          <p className="text-[22px] font-semibold leading-tight sm:text-[32px]">
            {site.barangay_name}
          </p>
          <p className="text-[13px] sm:text-[16px]">{site.place}</p>
        </div>
      </div>
    </div>
  );
}

export function SiteFooter() {
  // Empty fields are hidden.
  const { site } = useSite();
  const details = [
    site.office_hours && { label: "Office hours", value: site.office_hours },
    site.address && { label: "Address", value: site.address },
    site.hotline && {
      label: "Hotline",
      value: (
        <a href={`tel:${site.hotline}`} className={`text-white underline ${FOCUS_LINK}`}>
          {site.hotline}
        </a>
      ),
    },
  ].filter(Boolean) as { label: string; value: ReactNode }[];

  // One bar. The seal and the barangay's name are already in the masthead, and
  // nothing here claims to be an official government site.
  return (
    <footer className={`mt-16 border-t-4 border-brand ${TOP_BAR}`}>
      <div className={`${WIDTH} flex flex-wrap gap-x-6 gap-y-2 py-4 text-[15px]`}>
        {details.map((d) => (
          <span key={d.label}>
            <span className="text-white/80">{d.label}</span> {d.value}
          </span>
        ))}
        <Link to="/terms" className={`text-white underline ${FOCUS_LINK}`}>
          Terms of Use
        </Link>
        <Link to="/privacy" className={`text-white underline ${FOCUS_LINK}`}>
          Privacy Notice
        </Link>
        <span className="text-white/80">
          Made with Barangay V by BS IT students of Mapúa University
        </span>
      </div>
    </footer>
  );
}

// Sign in and register. Same chrome as the signed-in screens, minus the menu.
export function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <SkipLink />
      <header>
        <TopBar />
        <Masthead />
      </header>
      <div className="h-2.5 bg-brand" />
      <main id="main" className="flex-1 px-4 py-10">
        {children}
      </main>
      <SiteFooter />
    </div>
  );
}
