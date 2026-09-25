import { useState } from "react";
import { useNavigate } from "react-router-dom";

import * as api from "../api/client";
import { Button } from "../components/ui";
import { usePageTitle } from "../lib/usePageTitle";
import { useSession, useUser } from "../session-context";

// Where a resident lands until staff confirm they live in the barangay.
// Bilingual, because only residents ever see it.
export function Waiting() {
  usePageTitle("Waiting for approval");
  const user = useUser();
  const { refresh } = useSession();
  const navigate = useNavigate();
  const [checking, setChecking] = useState(false);
  const [still, setStill] = useState(false);
  const [resent, setResent] = useState<"" | "sent" | "failed">("");

  const resend = async () => {
    setResent("");
    try {
      await api.requestVerifyEmail(user.email);
      setResent("sent");
    } catch {
      setResent("failed");
    }
  };

  const checkAgain = async () => {
    setChecking(true);
    setStill(false);
    try {
      const fresh = await refresh();
      // Leaving while still pending would bounce straight back here and lose
      // the "not yet" message, so only go once something changed.
      if (fresh?.approval_status === "approved") {
        navigate("/");
        return;
      }
      setStill(true);
    } finally {
      setChecking(false);
    }
  };

  if (user.approval_status === "rejected") {
    return (
      <div className="max-w-xl border-t-2 border-ink pt-5">
        <h1 className="text-[32px] font-bold leading-tight tracking-tight">
          Account not approved
        </h1>
        <p className="mt-1 text-[19px] text-muted">Hindi naaprubahan ang account</p>
        <p className="mt-6 text-[19px]">
          Visit the barangay office if you think this is a mistake
        </p>
        <p className="mt-1 text-[19px] text-muted">
          Pumunta po sa barangay hall kung sa tingin ninyo ay mali ito
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-xl border-t-2 border-ink pt-5">
      <h1 className="text-[32px] font-bold leading-tight tracking-tight">
        Waiting for approval
      </h1>
      <p className="mt-1 text-[19px] text-muted">Hinihintay pa ang pag-apruba</p>

      {!user.is_verified && (
        <div className="mt-6 border-l-4 border-brand pl-3">
          <p className="text-[19px] font-bold">
            First, confirm your email · Una, kumpirmahin ang email ninyo
          </p>
          <p className="mt-1">
            We sent a link to {user.email} · Nagpadala kami ng link sa {user.email}
          </p>
          <p
            role="status"
            aria-live="polite"
            className={resent ? "mt-2 font-bold" : "sr-only"}
          >
            {resent === "sent"
              ? "Sent, check spam too · Naipadala na, tingnan din ang spam"
              : resent === "failed"
                ? "Didn't send, try again · Hindi naipadala, subukan ulit"
                : ""}
          </p>
          <Button variant="secondary" className="mt-3" onClick={resend}>
            Send it again · Ipadala ulit
          </Button>
        </div>
      )}

      <p className="mt-6 text-[19px]">
        {user.is_verified
          ? "Barangay staff will check that you live here"
          : "Then barangay staff will check that you live here"}
      </p>
      <p className="mt-1 text-[19px] text-muted">Titingnan ng barangay kung taga-rito kayo</p>

      <p
        role="status"
        aria-live="polite"
        className={still ? "mt-6 border-l-4 border-rule pl-3 font-bold" : "sr-only"}
      >
        {still ? "Not yet · Hindi pa po" : ""}
      </p>

      <Button variant="secondary" className="mt-6" disabled={checking} onClick={checkAgain}>
        {checking ? "Checking" : "Check again · Tingnan ulit"}
      </Button>
    </div>
  );
}
