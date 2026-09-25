import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import * as api from "../api/client";
import { FOCUS_BUTTON } from "./ui";
import { timeAgo } from "../lib/format";
import { useUser } from "../session-context";
import type { Notification } from "../api/types";

export function NotificationBell() {
  const user = useUser();
  const navigate = useNavigate();
  const [items, setItems] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const load = async () => {
    const page = await api.listNotifications(user);
    setItems(page.items);
    setUnreadCount(page.unread_count);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.id]);

  // Close on an outside click, the standard pattern for a dropdown panel.
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const openNotification = async (notification: Notification) => {
    if (!notification.is_read) {
      await api.markNotificationRead(user, notification.id);
      await load();
    }
    setOpen(false);
    if (notification.request_id) {
      navigate(`/requests/${notification.request_id}`);
    }
  };

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ""}`}
        onClick={() => setOpen((v) => !v)}
        className={`relative inline-flex items-center border-2 border-ink bg-white px-3 py-2 font-bold ${FOCUS_BUTTON}`}
      >
        Notifications
        {unreadCount > 0 && (
          <span className="ml-2 inline-flex h-5 min-w-5 items-center justify-center bg-brand px-1 text-[13px] font-bold text-white">
            {unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-10 mt-2 w-80 max-w-[calc(100vw-2rem)] border-2 border-ink bg-white shadow-[0_3px_0_#0b0c0c]">
          {items.length === 0 ? (
            <p className="p-4 text-muted">Nothing here yet</p>
          ) : (
            <ul>
              {items.map((n) => (
                <li key={n.id} className="border-b border-rule last:border-0">
                  <button
                    type="button"
                    onClick={() => openNotification(n)}
                    className={`block w-full px-4 py-3 text-left hover:bg-wash ${FOCUS_BUTTON} ${
                      n.is_read ? "" : "font-bold"
                    }`}
                  >
                    <span className="block">{n.message}</span>
                    <span className="mt-1 block text-[13px] font-normal text-muted">
                      {n.reference_number && `${n.reference_number} · `}
                      {timeAgo(n.created_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}