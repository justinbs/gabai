import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
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
import type { Role } from "./api/types";

// Navigation convenience, not access control. The server enforces scope on every
// endpoint. What the role check does prevent is a citizen reaching a staff
// screen by typing the URL, which would show them the queue table and the
// confidence scores residents are deliberately never given.
function Protected({ roles }: { roles: Role[] }) {
  const { user } = useSession();
  if (!user) return <Navigate to="/" replace />;
  return roles.includes(user.role) ? <AppShell /> : <Navigate to="/" replace />;
}

function Landing() {
  const { user } = useSession();
  if (!user) return <Login />;
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

          <Route element={<Protected roles={CITIZEN} />}>
            <Route path="/submit" element={<Submit />} />
            <Route path="/requests" element={<MyRequests />} />
          </Route>

          <Route element={<Protected roles={STAFF} />}>
            <Route path="/queue" element={<StaffQueue />} />
            <Route path="/review" element={<ReviewQueue />} />
          </Route>

          <Route element={<Protected roles={ADMIN} />}>
            <Route path="/admin/accounts" element={<AdminUsers />} />
            <Route path="/admin/routing" element={<AdminRouting />} />
            <Route path="/admin/audit" element={<AdminAudit />} />
          </Route>

          {/* Both audiences read this one. It branches on role internally. */}
          <Route element={<Protected roles={EVERYONE} />}>
            <Route path="/requests/:id" element={<RequestDetail />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  );
}
