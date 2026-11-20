import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import api, { getApiError } from "../services/api";
import useResource from "../hooks/useResource";
import Icon from "../components/Icon";
import { AssetPicker, LocationPicker } from "../components/pickers";
import { Alert, Button, Card, Field, PageHeader } from "../components/ui";
import { newRequestId } from "../utils/issues";

const EMPTY = {
  title: "",
  description: "",
  departmentId: "",
  categoryId: "",
  locationId: null,
  assetId: null,
  people: "",
  anonymous: false,
};

export default function NewComplaint() {
  const [form, setForm] = useState(EMPTY);
  const departments = useResource("/reference/departments");
  const categories = useResource("/reference/categories");
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [existingId, setExistingId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(null);
  // One id per submission attempt: a retry after a network error cannot create a duplicate.
  const requestId = useRef(newRequestId());

  const visibleCategories = (categories.data || []).filter(
    (category) => !form.departmentId || category.department_id === Number(form.departmentId),
  );

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: "" }));
  }

  async function submit(event) {
    event.preventDefault();
    if (loading) return;
    const invalid = {};
    if (form.title.trim().length < 3) invalid.title = "Add a short title with at least 3 characters.";
    if (form.description.trim().length < 10) invalid.description = "Describe the problem in at least 10 characters.";
    if (!form.locationId) invalid.locationId = "Choose the exact location.";
    setErrors(invalid);
    setError("");
    setExistingId(null);
    if (Object.keys(invalid).length) {
      document.getElementById(Object.keys(invalid)[0] === "locationId" ? "loc-0" : Object.keys(invalid)[0])?.focus();
      return;
    }
    setLoading(true);
    try {
      const body = {
        title: form.title.trim(),
        description: form.description.trim(),
        location_id: form.locationId,
        is_anonymous: form.anonymous,
        client_request_id: requestId.current,
      };
      if (form.departmentId) body.department_id = Number(form.departmentId);
      if (form.categoryId) body.category_id = Number(form.categoryId);
      if (form.assetId) body.asset_id = form.assetId;
      if (form.people) body.people_affected = Number(form.people);
      const { data } = await api.post("/complaints", body, { timeout: 120000 });
      setSubmitted(data);
    } catch (requestError) {
      const data = requestError.response?.data;
      if (data?.code === "already_reported") setExistingId(data.complaint_id);
      setError(getApiError(requestError, "We couldn’t submit your complaint. Your details are still here."));
    } finally {
      setLoading(false);
    }
  }

  if (submitted)
    return (
      <div className="mx-auto max-w-2xl py-5">
        <Card className="p-7 text-center sm:p-10">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-brand-50 text-brand-600">
            <Icon name="checkCircle" size={32} />
          </div>
          <p className="eyebrow mt-6">Your concern is on record</p>
          <h1 className="text-2xl font-semibold tracking-tight text-brand-900">Complaint submitted</h1>
          <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-5 text-left">
            <p className="text-xs text-slate-500">Complaint #{submitted.complaint_id} · Ticket {submitted.ticket_no}</p>
            <p className="mt-2 text-sm font-semibold text-slate-800">{submitted.status_label}</p>
            <p className="mt-1 text-sm text-slate-600">{submitted.message}</p>
          </div>
          {submitted.warning && <Alert variant="info" className="mt-4 text-left">{submitted.warning}</Alert>}
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Link className="btn btn-primary" to={`/complaints/${submitted.complaint_id}`}>Track this complaint</Link>
            <Link className="btn btn-secondary" to="/complaints">All my complaints</Link>
          </div>
        </Card>
      </div>
    );

  return (
    <div className="page-stack mx-auto max-w-3xl">
      <PageHeader eyebrow="New complaint" title="Tell us what needs fixing" description="Choose the exact place and item so similar reports are grouped into one ticket." />
      <Card className="p-6">
        <form onSubmit={submit} className="space-y-5" noValidate>
          {(departments.error || categories.error) && (
            <Alert variant="error">
              Couldn’t load all department and category options.{" "}
              <button type="button" className="underline" onClick={() => {
                if (departments.error) departments.refresh();
                if (categories.error) categories.refresh();
              }}>Try again</button>
            </Alert>
          )}
          {error && (
            <Alert variant="error">
              {error}{" "}
              {existingId && <Link className="underline" to={`/complaints/${existingId}`}>View your existing complaint</Link>}
            </Alert>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Department" htmlFor="departmentId" hint="Choose “Not sure” and we will route it for you.">
              <select id="departmentId" className="input" value={form.departmentId}
                onChange={(e) => setForm((c) => ({ ...c, departmentId: e.target.value, categoryId: "", assetId: null }))}>
                <option value="">Not sure</option>
                {(departments.data || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </Field>
            <Field label="Category" htmlFor="categoryId">
              <select id="categoryId" className="input" value={form.categoryId} onChange={(e) => update("categoryId", e.target.value)}>
                <option value="">Not sure</option>
                {visibleCategories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </Field>
          </div>
          <LocationPicker value={form.locationId} onChange={(id) => { update("locationId", id); update("assetId", null); }} error={errors.locationId} />
          <AssetPicker locationId={form.locationId} departmentId={form.departmentId} value={form.assetId} onChange={(id) => update("assetId", id)} />
          <Field label="Title" htmlFor="title" error={errors.title}>
            <input id="title" className="input" maxLength={200} value={form.title} onChange={(e) => update("title", e.target.value)} aria-invalid={Boolean(errors.title)} />
          </Field>
          <Field label="Describe the problem" htmlFor="description" error={errors.description}>
            <textarea id="description" className="input min-h-32" maxLength={4000} value={form.description} onChange={(e) => update("description", e.target.value)} aria-invalid={Boolean(errors.description)} />
          </Field>
          <Field label="How many people are affected? (optional)" htmlFor="people" hint="This is only a hint for staff. It does not change the priority.">
            <input id="people" className="input max-w-40" type="number" min="0" max="100000" inputMode="numeric" value={form.people} onChange={(e) => update("people", e.target.value)} />
          </Field>
          <label className="flex items-start gap-3 rounded-xl border border-slate-200 p-4 text-sm">
            <input type="checkbox" className="mt-1" checked={form.anonymous} onChange={(e) => update("anonymous", e.target.checked)} />
            <span>
              <strong>Submit anonymously.</strong> Staff and admins will not see your name. Names, emails, phone and
              enrollment numbers in your text are removed automatically, but please avoid naming people.
            </span>
          </label>
          <div className="flex justify-end gap-3">
            <Link className="btn btn-secondary" to="/complaints">Cancel</Link>
            <Button type="submit" loading={loading}>Submit complaint</Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
