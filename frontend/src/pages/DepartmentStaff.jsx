import { Link } from "react-router-dom";
import useResource from "../hooks/useResource";
import { Badge, Card, EmptyState, ErrorState, PageHeader, TableSkeleton } from "../components/ui";

export default function DepartmentStaff() {
  const staff = useResource("/department-staff");
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Department" title="Staff workload" description="Who is busy and who has capacity."
        actions={<Link className="btn btn-secondary" to="/department">Back to queue</Link>} />
      <Card>
        {staff.loading ? <TableSkeleton /> : staff.error ? <ErrorState message={staff.error} onRetry={staff.refresh} /> : staff.data.length === 0 ? (
          <EmptyState icon="users" title="No staff yet" description="A super admin can add staff to this department." />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <caption className="sr-only">Staff and their current workload</caption>
              <thead><tr><th scope="col">Name</th><th scope="col">Active tasks</th><th scope="col">Overdue</th></tr></thead>
              <tbody>
                {staff.data.map((s) => (
                  <tr key={`${s.id}-${s.department_id}`}>
                    <td className="font-medium text-slate-800">{s.name}</td>
                    <td>{s.active_tasks}</td>
                    <td>{s.overdue_tasks ? <Badge tone="red">{s.overdue_tasks}</Badge> : "0"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
