import { useState } from "react";
import { Link } from "react-router-dom";
import api, { getApiError } from "../services/api";
import Icon from "../components/Icon";
import {
  Alert,
  Badge,
  Button,
  Card,
  Field,
  PageHeader,
  StatusBadge,
} from "../components/ui";

export default function NewComplaint() {
  const [form, setForm] = useState({ title: "", description: "", people: "1" });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(null);
  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: "" }));
  }
  async function submit(event) {
    event.preventDefault();
    if (loading) return;
    const invalid = {};
    if (form.title.trim().length < 3)
      invalid.title = "Add a short title with at least 3 characters.";
    if (form.description.trim().length < 10)
      invalid.description = "Describe the concern in at least 10 characters.";
    const people = Number(form.people);
    if (!Number.isSafeInteger(people) || people < 1 || people > 1000000)
      invalid.people = "Enter a whole number from 1 to 1,000,000.";
    setErrors(invalid);
    setError("");
    if (Object.keys(invalid).length) {
      document.getElementById(Object.keys(invalid)[0])?.focus();
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.post(
        "/complaints",
        {
          title: form.title.trim(),
          description: form.description.trim(),
          people_affected: people,
        },
        { timeout: 120000 },
      );
      setSubmitted(data);
    } catch (requestError) {
      setError(
        getApiError(
          requestError,
          "We couldn’t submit your complaint. Your details are still here.",
        ),
      );
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
          <h1 className="text-2xl font-semibold tracking-tight text-brand-900">
            Complaint submitted successfully.
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-500">
            You can now follow its progress from your workspace.
          </p>
          <div className="mt-7 rounded-xl border border-slate-200 bg-slate-50 p-5 text-left">
            <p className="text-xs text-slate-500">Complaint #{submitted.id}</p>
            <h2 className="mt-2 text-base font-semibold text-slate-700">
              {submitted.title}
            </h2>
            <div className="mt-4 flex flex-wrap gap-2">
              <StatusBadge status={submitted.status} />
              {submitted.category && <Badge>{submitted.category}</Badge>}
            </div>
          </div>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Link
              to={`/complaints/${submitted.id}`}
              className="btn btn-primary"
            >
              View complaint <Icon name="arrowRight" size={16} />
            </Link>
            <Link to="/complaints" className="btn btn-secondary">
              Back to overview
            </Link>
          </div>
        </Card>
      </div>
    );
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Make a difference"
        title="Let’s get it resolved."
        description="Tell us what needs attention. Clear details help your concern reach the right team."
      />
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(260px,1fr)]">
        <Card>
          <div className="panel-heading">
            <div>
              <h2>Complaint details</h2>
              <p>All fields are required.</p>
            </div>
            <Icon name="file" size={19} className="text-brand-500" />
          </div>
          <form onSubmit={submit} className="space-y-6 p-5 sm:p-7">
            <Field
              label="What’s the concern?"
              htmlFor="title"
              hint={`${form.title.length}/200 characters · A short, specific title works best.`}
              error={errors.title}
            >
              <input
                id="title"
                name="title"
                className="input"
                placeholder="e.g. Water supply interrupted in Block B"
                required
                minLength={3}
                maxLength={200}
                value={form.title}
                onChange={(event) => update("title", event.target.value)}
                aria-invalid={Boolean(errors.title)}
                aria-describedby={`title-hint${errors.title ? " title-error" : ""}`}
                disabled={loading}
              />
            </Field>
            <Field
              label="Tell us more"
              htmlFor="description"
              hint={`${form.description.length.toLocaleString()}/10,000 characters · Include the location, timing, and impact.`}
              error={errors.description}
            >
              <textarea
                id="description"
                name="description"
                className="input min-h-44"
                rows={7}
                placeholder="Describe what happened, where it happened, and how it is affecting you…"
                required
                minLength={10}
                maxLength={10000}
                value={form.description}
                onChange={(event) => update("description", event.target.value)}
                aria-invalid={Boolean(errors.description)}
                aria-describedby={`description-hint${errors.description ? " description-error" : ""}`}
                disabled={loading}
              />
            </Field>
            <Field
              label="How many people are affected?"
              htmlFor="people"
              hint="Include yourself. Your best estimate helps us understand the impact."
              error={errors.people}
            >
              <input
                id="people"
                name="people"
                type="number"
                inputMode="numeric"
                className="input max-w-40"
                min={1}
                max={1000000}
                step={1}
                required
                value={form.people}
                onChange={(event) => update("people", event.target.value)}
                aria-invalid={Boolean(errors.people)}
                aria-describedby={`people-hint${errors.people ? " people-error" : ""}`}
                disabled={loading}
              />
            </Field>
            {error && <Alert variant="error">{error}</Alert>}
            {loading && (
              <Alert>
                We’re submitting and analyzing your concern. This may take a
                moment; keep this page open.
              </Alert>
            )}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-5">
              <Link
                to="/complaints"
                className={`btn btn-ghost ${loading ? "pointer-events-none opacity-50" : ""}`}
                aria-disabled={loading}
                tabIndex={loading ? -1 : undefined}
              >
                Cancel
              </Link>
              <Button type="submit" loading={loading}>
                {loading ? "Submitting…" : "Submit complaint"}
                {!loading && <Icon name="arrowRight" size={16} />}
              </Button>
            </div>
          </form>
        </Card>
        <aside className="space-y-5">
          <Card className="border-brand-100 bg-brand-50 p-6">
            <span className="inline-flex rounded-xl border border-brand-100 bg-white p-2.5 text-brand-600">
              <Icon name="sparkles" size={22} />
            </span>
            <h2 className="mt-4 text-base font-semibold text-brand-900">
              A clearer path to the right team.
            </h2>
            <p className="mt-3 text-xs leading-6 text-slate-600">
              Your complaint is analyzed to help determine its category,
              priority, and department. Similar reports help identify recurring
              concerns.
            </p>
          </Card>
          <Card className="p-6">
            <h2 className="text-sm font-semibold text-slate-700">
              A helpful report includes
            </h2>
            <ul className="mt-4 space-y-4">
              {[
                [
                  "A specific location",
                  "Building, room, area, or service affected.",
                ],
                ["When it started", "Mention dates or how often it happens."],
                ["The impact", "Explain what you’re unable to do."],
              ].map(([title, description]) => (
                <li key={title} className="flex items-start gap-3">
                  <Icon
                    name="check"
                    size={16}
                    className="mt-0.5 text-brand-500"
                  />
                  <div>
                    <h3 className="text-xs font-medium text-slate-700">
                      {title}
                    </h3>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      {description}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </aside>
      </div>
    </div>
  );
}
