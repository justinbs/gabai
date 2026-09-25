import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { BARANGAY } from "../lib/barangay";
import type { User } from "../api/types";
import { FOCUS_LINK } from "./ui";

// Layout follows DICT's government website template: dark top bar, masthead
// with the seal and the office's name, and an agency footer over a standard
// footer. Adapted, not copied. No Republic Seal (its use is restricted and this
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
  return (
    <div className="bg-white">
      <div className={`${WIDTH} flex items-center gap-4 py-4 sm:py-5`}>
        <img
          src="/barangay-logo.jpg"
          alt="Barangay V logo"
          className="h-16 w-16 shrink-0 object-contain sm:h-[100px] sm:w-[100px]"
        />
        <div className="font-masthead text-[#222222]">
          <p className="text-[13px] tracking-wide sm:text-[16px]">Republika ng Pilipinas</p>
          <div className="my-1 h-px bg-[#222222]" />
          <p className="text-[22px] font-semibold leading-tight sm:text-[32px]">
            {BARANGAY.name}
          </p>
          <p className="text-[13px] sm:text-[16px]">{BARANGAY.place}</p>
        </div>
      </div>
    </div>
  );
}

export function SiteFooter() {
  // Only what the barangay has confirmed. See lib/barangay.ts.
  const details = [
    BARANGAY.officeHours && { label: "Office hours", value: BARANGAY.officeHours },
    BARANGAY.address && { label: "Address", value: BARANGAY.address },
    BARANGAY.hotline && {
      label: "Hotline",
      value: (
        <a href={`tel:${BARANGAY.hotline}`} className={`text-link underline ${FOCUS_LINK}`}>
          {BARANGAY.hotline}
        </a>
      ),
    },
  ].filter(Boolean) as { label: string; value: ReactNode }[];

  return (
    <footer className="mt-16">
      <div className="border-t-4 border-brand bg-wash">
        <div className={`${WIDTH} grid gap-6 py-8 sm:grid-cols-2`}>
          <div className="flex items-start gap-3">
            <img src="/barangay-logo.jpg" alt="" className="h-12 w-12 shrink-0 object-contain" />
            <div>
              <p className="font-masthead text-[19px] font-semibold">{BARANGAY.name}</p>
              <p className="text-muted">{BARANGAY.place}</p>
            </div>
          </div>
          {details.length > 0 && (
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
              {details.map((d) => (
                <div key={d.label} className="contents">
                  <dt className="text-muted">{d.label}</dt>
                  <dd>{d.value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </div>
      <div className={TOP_BAR}>
        <div className={`${WIDTH} flex flex-wrap gap-x-6 gap-y-2 py-4 text-[15px]`}>
          <span>Republika ng Pilipinas</span>
          <a href="https://www.gov.ph" className={`text-white underline ${FOCUS_LINK}`}>
            GOV.PH
          </a>
          <span className="text-white/80">
            Made with Barangay V by BS IT students of Mapúa University
          </span>
        </div>
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
