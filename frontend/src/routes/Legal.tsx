import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import * as api from "../api/client";
import { ApiError } from "../api/http";
import { LegalText } from "../components/LegalText";
import { PublicShell } from "../components/SiteChrome";
import { Button, FOCUS_LINK } from "../components/ui";
import { TERMS_EFFECTIVE, TERMS_VERSION, privacyNotice, termsOfUse } from "../content/terms";
import { usePageTitle } from "../lib/usePageTitle";
import { useSession } from "../session-context";
import { useSite } from "../site-context";

export function TermsPage() {
  usePageTitle("Terms of Use");
  const { site } = useSite();
  const doc = termsOfUse(site);
  return (
    <PublicShell>
      <div className="mx-auto max-w-3xl">
        <h1 className="text-[36px] font-bold tracking-tight">{doc.title}</h1>
        <p className="mt-1 text-[19px] text-muted">
          {doc.tagalog} · Effective {TERMS_EFFECTIVE}
        </p>
        <div className="mt-8">
          <LegalText doc={doc} />
        </div>
        <p className="mt-10">
          <Link to="/privacy" className={`text-link underline ${FOCUS_LINK}`}>
            Read the Privacy Notice
          </Link>
        </p>
      </div>
    </PublicShell>
  );
}

export function PrivacyPage() {
  usePageTitle("Privacy Notice");
  const { site } = useSite();
  const doc = privacyNotice(site);
  return (
    <PublicShell>
      <div className="mx-auto max-w-3xl">
        <h1 className="text-[36px] font-bold tracking-tight">{doc.title}</h1>
        <p className="mt-1 text-[19px] text-muted">
          {doc.tagalog} · Effective {TERMS_EFFECTIVE}
        </p>
        <div className="mt-8">
          <LegalText doc={doc} />
        </div>
        <p className="mt-10">
          <Link to="/terms" className={`text-link underline ${FOCUS_LINK}`}>
            Read the Terms of Use
          </Link>
        </p>
      </div>
    </PublicShell>
  );
}

// Shown when the account hasn't accepted the current version.
export function AcceptTerms() {
  usePageTitle("Terms and privacy");
  const { site } = useSite();
  const { refresh, signOut } = useSession();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const accept = async () => {
    setBusy(true);
    setError("");
    try {
      await api.acceptTerms(TERMS_VERSION);
      await refresh();
      navigate("/", { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 409
          ? "The text changed while this page was open. Reload the page · Nagbago ang teksto, i-reload po ang page"
          : "Didn't save, try again · Hindi nai-save, subukan ulit",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-3xl pt-4">
      <h1 className="text-[32px] font-bold leading-tight tracking-tight">Before you continue</h1>
      <p className="mt-1 text-[19px] text-muted">Bago magpatuloy</p>
      <p className="mt-6 text-[19px]">
        Please read how GABAI works and how your data is handled, then agree to continue ·
        Basahin po kung paano gumagana ang GABAI at paano hinahawakan ang inyong datos
      </p>

      <div className="mt-8 border-2 border-ink p-5">
        <h2 className="text-[28px] font-bold">{termsOfUse(site).title}</h2>
        <div className="mt-4">
          <LegalText doc={termsOfUse(site)} level={3} />
        </div>
        <h2 className="mt-12 text-[28px] font-bold">{privacyNotice(site).title}</h2>
        <div className="mt-4">
          <LegalText doc={privacyNotice(site)} level={3} />
        </div>
      </div>

      <p role="alert" className={error ? "mt-4 border-l-4 border-danger p-3 font-bold text-danger" : "sr-only"}>
        {error}
      </p>
      <div className="mt-6 flex flex-wrap items-center gap-4">
        <Button onClick={accept} disabled={busy}>
          {busy ? "Saving" : "I agree · Sang-ayon ako"}
        </Button>
        <Button variant="secondary" onClick={() => signOut()}>
          Sign out
        </Button>
      </div>
    </div>
  );
}
