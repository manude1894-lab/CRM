import React, { useEffect, useRef, useState } from "react";
import { notificationsApi } from "../api/endpoints";
import { Icon } from "./ui";

const POLL_MS = 45000;

export default function NotificationBell() {
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState([]);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const pollUnread = async () => {
    try {
      const { unread_count } = await notificationsApi.unreadCount();
      setUnreadCount(unread_count);
    } catch {
      // best-effort polling — ignore transient failures
    }
  };

  useEffect(() => {
    pollUnread();
    const interval = setInterval(pollUnread, POLL_MS);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const onClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const togglePanel = async () => {
    const next = !open;
    setOpen(next);
    if (next) {
      try {
        const list = await notificationsApi.list({ limit: 20 });
        setNotifications(list);
      } catch {
        setNotifications([]);
      }
    }
  };

  const markRead = async (n) => {
    if (!n.read_at) {
      try {
        await notificationsApi.markRead(n.id);
        setNotifications((prev) => prev.map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x)));
        setUnreadCount((c) => Math.max(0, c - 1));
      } catch {
        // ignore
      }
    }
  };

  const markAllRead = async () => {
    try {
      await notificationsApi.markAllRead();
      setNotifications((prev) => prev.map((x) => ({ ...x, read_at: x.read_at || new Date().toISOString() })));
      setUnreadCount(0);
    } catch {
      // ignore
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button onClick={togglePanel} className="relative text-gray-400 hover:text-gray-600 p-1.5 rounded" title="Notifications">
        <Icon name="bell" size={18} />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 px-1 flex items-center justify-center">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl border border-gray-100 shadow-2xl z-50 max-h-96 overflow-y-auto">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <span className="text-sm font-semibold text-gray-800">Notifications</span>
            {unreadCount > 0 && (
              <button onClick={markAllRead} className="text-xs text-blue-600 hover:underline">Mark all read</button>
            )}
          </div>
          {notifications.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-6">No notifications yet.</p>
          )}
          {notifications.map((n) => (
            <button key={n.id} onClick={() => markRead(n)}
              className={`w-full text-left px-4 py-3 border-b border-gray-50 hover:bg-gray-50 ${!n.read_at ? "bg-blue-50/40" : ""}`}>
              <p className="text-xs text-gray-700 leading-snug">{n.message}</p>
              <p className="text-[10px] text-gray-400 mt-1">{new Date(n.created_at).toLocaleString()}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
