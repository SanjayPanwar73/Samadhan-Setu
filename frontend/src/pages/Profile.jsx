import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import {
  getDisplayName,
  getHomeRouteForRole,
  ROLE_LABELS,
} from "../utils/auth";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  PageHeader,
  PageSkeleton,
} from "../components/ui";
import Icon from "../components/Icon";

export default function Profile() {
  const { user, role, loading, error, refreshUser } = useAuth();
  if (loading && !user) return <PageSkeleton />;
  if (error)
    return (
      <Card>
        <ErrorState message={error} onRetry={() => refreshUser()} />
      </Card>
    );
  const name = getDisplayName(user);
  return (
    <div className="page-stack mx-auto max-w-4xl">
      <PageHeader
        eyebrow="Your account"
        title="My profile"
        description="Your identity and access in the Samadhan Setu workspace."
        actions={
          <Button
            variant="secondary"
            loading={loading}
            onClick={() => refreshUser()}
          >
            <Icon name="refresh" size={16} />
            Refresh
          </Button>
        }
      />
      <Card className="overflow-hidden">
        <div className="h-24 border-b border-brand-100 bg-brand-50" />
        <div className="px-6 pb-7 sm:px-8">
          <div className="-mt-8 flex flex-wrap items-end justify-between gap-4">
            <div>
              <span className="grid h-16 w-16 place-items-center rounded-2xl border-4 border-white bg-brand-600 text-xl font-semibold text-white shadow-sm">
                {name
                  .split(" ")
                  .slice(0, 2)
                  .map((part) => part[0])
                  .join("")}
              </span>
              <h2 className="mt-4 text-xl font-semibold tracking-tight text-brand-900">
                {name}
              </h2>
              <p className="mt-1 text-sm text-slate-500">{user?.email}</p>
            </div>
            <Badge tone="green">{ROLE_LABELS[role] || role}</Badge>
          </div>
          <dl className="mt-7 grid gap-6 border-t border-slate-100 pt-6 sm:grid-cols-2">
            {[
              ["Full name", user?.name],
              ["Email address", user?.email],
              ["Workspace role", ROLE_LABELS[role] || role],
              ["Account ID", user?.id ? `#${user.id}` : null],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs text-slate-500">{label}</dt>
                <dd className="mt-2 break-words text-sm font-medium text-slate-700">
                  {value || "Not available"}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </Card>
      <Card className="flex flex-wrap items-start gap-4 p-6">
        <span className="rounded-xl bg-brand-50 p-3 text-brand-600">
          <Icon name="shield" size={23} />
        </span>
        <div className="flex-1">
          <h2 className="text-sm font-semibold text-slate-700">
            Your workspace access
          </h2>
          <p className="mt-2 text-xs leading-6 text-slate-500">
            {role === "user"
              ? "Submit concerns, follow your complaints, and share feedback on completed resolutions."
              : role === "staff"
                ? "Review complaints and take action on those assigned to you."
                : role === "admin"
                  ? "Manage departments and team accounts, assign concerns, and oversee resolutions."
                  : "Review complaint trends, SLA performance, and the priority queue."}
          </p>
          <Link
            to={getHomeRouteForRole(role)}
            className="mt-4 inline-flex items-center gap-2 text-xs font-semibold text-brand-600 hover:underline"
          >
            Open workspace <Icon name="arrowRight" size={14} />
          </Link>
        </div>
      </Card>
    </div>
  );
}
