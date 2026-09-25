import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import * as api from "../api/client";
import { FOCUS_LINK } from "../components/ui";
import { usePageTitle } from "../lib/usePageTitle";
import { useSession, useUser } from "../session-context";

// Where a resident lands until their email is confirmed and staff approve them.
// Bilingual, because only residents ever see it.
export function Waiting() {
  usePageTitle("Waiting for approval");
  const user = useUser();
  const { refresh } = useSession();
  const navigate = useNavigate();
  const [resent, setResent] = useState<"" | "sent" | "failed">("");

  // No "check again" button. When they come back to this tab, usually after
  // clicking the email link, look again and move on if they've been approved.
  useEffect(() => {
    const recheck = async () => {
      if (document.visibilityState !== "visible") return;
      const fresh = await refresh();
      if (fresh?.approval_status === "approved") navigate("/");
    };
    window.addEventListener("focus", recheck);
    document.addEventListener("visibilitychange", recheck);
    return () => {
      window.removeEventListener("focus", recheck);
      document.removeEventListener("visibilitychange", recheck);
    };
  }, [refresh, navigate]);

  const resend = async () => {
    setResent("");
    try {
      await api.requestVerifyEmail(user.email);
      setResent("sent");
    } catch {
      setResent("failed");
    }
  };

  if (user.approval_status === "rejected") {
    return (
      <div className="max-w-xl pt-4">
        <h1 className="text-[32px] font-bold leading-tight tracking-tight">
          Account not approved
        </h1>
        <p className="mt-1 text-[19px] text-muted">Hindi naaprubahan ang account</p>
        <p className="mt-6 text-[19px]">
          Visit the barangay office if you think this is a mistake · Pumunta po sa barangay
          hall kung sa tingin ninyo ay mali ito
        </p>
      </div>
    );
  }

  const confirmed = user.is_verified;

  return (
    <div className="max-w-xl pt-4">
      <h1 className="text-[32px] font-bold leading-tight tracking-tight">
        Waiting for approval
      </h1>
      <p className="mt-1 text-[19px] text-muted">Hinihintay pa ang pag-apruba</p>

      <ol className="mt-8 space-y-6">
        <Step
          number={1}
          title="Confirm your email · Kumpirmahin ang email"
          status={confirmed ? "Done · Tapos na" : "To do · Gagawin pa"}
          done={confirmed}
        >
          {!confirmed && (
            <>
              <p className="mt-1 text-muted">
                Link sent to <span className="break-all">{user.email}</span>
              </p>
              <button
                type="button"
                onClick={resend}
                className={`mt-1 text-link underline ${FOCUS_LINK}`}
              >
                Send it again · Ipadala ulit
              </button>
              <p role="status" aria-live="polite" className={resent ? "mt-1" : "sr-only"}>
                {resent === "sent"
                  ? "Sent, check spam too · Naipadala na, tingnan din ang spam"
                  : resent === "failed"
                    ? "Didn't send, try again · Hindi naipadala, subukan ulit"
                    : ""}
              </p>
            </>
          )}
        </Step>
        <Step
          number={2}
          title="Barangay checks you live here · Titingnan kung taga-rito kayo"
          status={confirmed ? "Waiting · Naghihintay" : "After step 1 · Pagkatapos ng una"}
          done={false}
        />
      </ol>
    </div>
  );
}

function Step({
  number,
  title,
  status,
  done,
  children,
}: {
  number: number;
  title: string;
  status: string;
  done: boolean;
  children?: React.ReactNode;
}) {
  return (
    <li className="flex gap-4">
      <span
        aria-hidden="true"
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full font-bold ${
          done ? "bg-brand text-white" : "border-2 border-ink"
        }`}
      >
        {number}
      </span>
      <div className="pt-1">
        <p className="text-[19px] font-bold">{title}</p>
        <p className={done ? "font-bold text-brand" : "text-muted"}>{status}</p>
        {children}
      </div>
    </li>
  );
}
