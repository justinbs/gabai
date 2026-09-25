import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { Account } from "./routes/Account";
import { ForgotPassword, ResetPassword, VerifyEmail } from "./routes/EmailLinks";
import { SignUps } from "./routes/SignUps";
import { Waiting } from "./routes/Waiting";
import { Login } from "./routes/Login";
import { MyRequests } from "./routes/MyRequests";
import { RequestDetail } from "./routes/RequestDetail";
import { ReviewQueue } from "./routes/ReviewQueue";
import { StaffQueue } from "./routes/StaffQueue";
import { AdminAudit } from "./routes/AdminAudit";
import { AdminRouting } from "./routes/AdminRouting";
import { AdminUsers } from "./routes/AdminUsers";
import { Register } from "./routes/Register";
import { Submit } from "./routes/Submit";
import { SessionProvider } from "./session";
import { useSession } from "./session-context";
import type { Role, User } from "./api/types";

// Where someone goes when the server won't let them do anything else yet.
function blockedHome(user: User): string | null {
  if (user.approval_status !== "approved") return "/waiting";
  if (user.must_change_password) return "/account";
  return null;
}

function Protected({ roles }: { roles: Role[] }) {
  const { user, initializing } = useSession();
  const { pathname } = useLocation();
  if (initializing) return null;
  if (!user) return <Navigate to="/" replace />;
  // The server already refuses everything else, these just avoid a screen full
  // of errors.
  const home = blockedHome(user);
  if (home && pathname !== home) return <Navigate to={home} replace />;
  return roles.includes(user.role) ? <AppShell /> : <Navigate to="/" replace />;
}

function Landing() {
  const { user, initializing } = useSession();
  if (initializing) return null;
  if (!user) return <Login />;
  const home = blockedHome(user);
  if (home) return <Navigate to={home} replace />;
  return <Navigate to={user.role === "citizen" ? "/requests" : "/queue"} replace />;
}

const CITIZEN: Role[] = ["citizen"];
const STAFF: Role[] = ["staff", "admin"];
const ADMIN: Role[] = ["admin"];
const EVERYONE: Role[] = ["citizen", "staff", "admin"];

export default function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/verify-email" element={<VerifyEmail />} />

          <Route element={<Protected roles={CITIZEN} />}>
            <Route path="/submit" element={<Submit />} />
            <Route path="/requests" element={<MyRequests />} />
          </Route>

          <Route element={<Protected roles={STAFF} />}>
            <Route path="/queue" element={<StaffQueue />} />
            <Route path="/review" element={<ReviewQueue />} />
            <Route path="/sign-ups" element={<SignUps />} />
          </Route>

          <Route element={<Protected roles={ADMIN} />}>
            <Route path="/admin/accounts" element={<AdminUsers />} />
            <Route path="/admin/routing" element={<AdminRouting />} />
            <Route path="/admin/audit" element={<AdminAudit />} />
          </Route>

          <Route element={<Protected roles={EVERYONE} />}>
            <Route path="/requests/:id" element={<RequestDetail />} />
            <Route path="/account" element={<Account />} />
            <Route path="/waiting" element={<Waiting />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  );
}