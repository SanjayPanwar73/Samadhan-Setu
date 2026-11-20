import { formatDate } from "../utils/complaints";

export default function Timeline({ events = [] }) {
  if (!events.length)
    return <p className="text-sm text-slate-500">No updates yet.</p>;
  return (
    <ol className="space-y-4" aria-label="Complaint timeline">
      {events.map((event, index) => (
        <li key={`${event.at}-${index}`} className="flex gap-3">
          <span
            className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-brand-500"
            aria-hidden="true"
          />
          <div>
            <p className="text-sm font-medium text-slate-800">{event.label}</p>
            <p className="text-xs text-slate-500">
              {formatDate(event.at, { time: true })}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
