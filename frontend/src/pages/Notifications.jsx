import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../services/api";

function formatDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function Notifications() {
  const [notifications, setNotifications] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchNotifications = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const response = await api.get("/notifications");
      setNotifications(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not load notifications.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void fetchNotifications());
  }, [fetchNotifications]);

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Notifications</h1>
          <p className="mt-1 text-sm text-slate-500">Recent activity on complaints connected to you.</p>
        </div>
        <button
          onClick={fetchNotifications}
          disabled={isLoading}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
        >
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </div>
      {isLoading && <div className="rounded-lg bg-white p-8 text-center text-sm text-slate-500">Loading notifications...</div>}
      {!isLoading && error && (
        <div className="rounded-lg bg-white p-8 text-center">
          <p className="text-sm text-red-600">{error}</p>
          <button onClick={fetchNotifications} className="mt-3 rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-white">
            Try again
          </button>
        </div>
      )}
      {!isLoading && !error && notifications.length === 0 && (
        <div className="rounded-lg bg-white p-8 text-center text-sm text-slate-500">
          You&apos;re all caught up. No notifications yet.
        </div>
      )}
      {!isLoading && !error && notifications.length > 0 && (
        <div className="divide-y divide-slate-100 overflow-hidden rounded-lg bg-white shadow">
          {notifications.map((notification) => (
            <div key={notification.id} className="flex items-start justify-between gap-4 p-4">
              <div>
                <p className="font-medium text-slate-800">{notification.title}</p>
                <p className="mt-1 text-sm text-slate-600">{notification.message}</p>
                <p className="mt-2 text-xs text-slate-400">{formatDate(notification.created_at)}</p>
              </div>
              {notification.complaint_id && (
                <Link to={`/complaints/${notification.complaint_id}`} className="shrink-0 text-sm font-medium text-slate-800 hover:underline">
                  View
                </Link>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default Notifications;
