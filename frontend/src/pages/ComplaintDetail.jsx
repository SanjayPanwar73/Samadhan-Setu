import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api, { getApiError } from "../services/api";
import useResource from "../hooks/useResource";
import Timeline from "../components/Timeline";
import FeedbackForm from "../components/FeedbackForm";
import { Alert, Badge, Button, Card, ErrorState, PageHeader, PageSkeleton } from "../components/ui";
import { formatDate } from "../utils/complaints";

export default function ComplaintDetail() {
  const { id } = useParams();
  const complaint = useResource(`/complaints/${id}`);
  const timeline = useResource(`/complaints/${id}/timeline`);
  const [uploadMessage, setUploadMessage] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef(null);

  async function upload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadMessage(null);
    const body = new FormData();
    body.append("file", file);
    body.append("kind", "evidence");
    try {
      await api.post(`/complaints/${id}/attachments`, body);
      setUploadMessage({ variant: "success", text: "File attached." });
    } catch (e) {
      setUploadMessage({ variant: "error", text: getApiError(e, "Could not attach the file.") });
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  if (complaint.loading && !complaint.data) return <PageSkeleton />;
  if (complaint.error) return <Card><ErrorState message={complaint.error} onRetry={complaint.refresh} /></Card>;
  const c = complaint.data;
  return (
    <div className="page-stack mx-auto max-w-4xl">
      <PageHeader
        eyebrow={`Complaint #${c.id}${c.ticket_no ? ` · ${c.ticket_no}` : ""}`}
        title={c.title}
        actions={<Link className="btn btn-secondary" to="/complaints">Back to list</Link>}
      />
      <Card className="p-6">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="blue">{c.status_label}</Badge>
          {c.is_anonymous && <Badge>Anonymous · {c.anon_code}</Badge>}
        </div>
        <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-slate-700">{c.description}</p>
        <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
          <div><dt className="text-xs text-slate-500">Department</dt><dd>{c.department_name || "Awaiting routing"}</dd></div>
          <div><dt className="text-xs text-slate-500">Category</dt><dd>{c.category_name || "—"}</dd></div>
          <div><dt className="text-xs text-slate-500">Location</dt><dd>{c.location_path || "—"}</dd></div>
          <div><dt className="text-xs text-slate-500">Item</dt><dd>{c.asset_name || "Not specified"}</dd></div>
          <div><dt className="text-xs text-slate-500">Submitted</dt><dd>{formatDate(c.created_at, { time: true })}</dd></div>
        </dl>
        <p className="mt-5 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">{c.shared_message}</p>
      </Card>

      {c.resolution_summary && (
        <Alert variant="success" title="How it was resolved">{c.resolution_summary}</Alert>
      )}
      {c.feedback_state === "pending" && (
        <Card className="p-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-800">Was it fixed?</h2>
          <FeedbackForm complaintId={c.id} onDone={() => { complaint.refresh(); timeline.refresh(); }} />
        </Card>
      )}
      {c.feedback_state === "submitted" && <Alert variant="info">Thanks, your feedback has been recorded.</Alert>}

      <Card className="p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-800">Progress</h2>
        {timeline.loading ? <PageSkeleton /> : <Timeline events={timeline.data || []} />}
      </Card>

      {!["closed", "rejected", "merged"].includes(c.status) && (
        <Card className="p-6">
          <h2 className="mb-2 text-lg font-semibold text-slate-800">Add a photo or PDF</h2>
          <p className="mb-3 text-sm text-slate-500">PNG, JPEG, WebP or PDF, up to 5 MB.</p>
          {uploadMessage && <Alert variant={uploadMessage.variant} className="mb-3">{uploadMessage.text}</Alert>}
          <input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp,application/pdf" onChange={upload} disabled={uploading} aria-label="Attach a file" />
          {uploading && <p className="mt-2 text-xs text-slate-500">Uploading…</p>}
        </Card>
      )}
      <div><Button variant="ghost" onClick={() => { complaint.refresh(); timeline.refresh(); }}>Refresh</Button></div>
    </div>
  );
}
