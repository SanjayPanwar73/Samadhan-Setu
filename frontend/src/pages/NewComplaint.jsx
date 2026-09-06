import { useState } from "react";
import { Link } from "react-router-dom";
import api from "../services/api";

function NewComplaint() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [peopleAffected, setPeopleAffected] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [submittedComplaint, setSubmittedComplaint] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    if (!title.trim() || !description.trim()) {
      setError("Please fill in both the title and description.");
      return;
    }

    setIsLoading(true);
    try {
      // Matches the backend's ComplaintCreate schema exactly.
      // No attachment field exists on this endpoint, so none is sent.
      const response = await api.post("/complaints", {
        title,
        description,
        people_affected: Number(peopleAffected) || 1,
      });

      setSubmittedComplaint(response.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === "string") {
        setError(detail);
      } else if (Array.isArray(detail) && detail.length > 0) {
        setError(detail[0].msg || "Please check the form and try again.");
      } else {
        setError("Something went wrong while submitting your complaint. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  }

  // Success state: show the backend's response and let the user
  // move on, instead of just resetting the form silently.
  if (submittedComplaint) {
    return (
      <div className="max-w-lg mx-auto bg-white rounded-lg shadow p-6">
        <h1 className="text-xl font-semibold text-green-700">
          Complaint submitted successfully
        </h1>

        <dl className="mt-4 space-y-2 text-sm text-slate-600">
          <div className="flex justify-between">
            <dt className="font-medium text-slate-500">Complaint ID</dt>
            <dd>#{submittedComplaint.id}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium text-slate-500">Status</dt>
            <dd className="capitalize">{submittedComplaint.status}</dd>
          </div>
          {submittedComplaint.category && (
            <div className="flex justify-between">
              <dt className="font-medium text-slate-500">Category</dt>
              <dd className="capitalize">{submittedComplaint.category}</dd>
            </div>
          )}
        </dl>

        <div className="mt-6 flex gap-3">
          <Link
            to={`/complaints/${submittedComplaint.id}`}
            className="flex-1 text-center rounded-md bg-slate-800 text-white text-sm font-medium py-2 hover:bg-slate-700"
          >
            View Complaint
          </Link>
          <Link
            to="/complaints"
            className="flex-1 text-center rounded-md border border-slate-300 text-slate-700 text-sm font-medium py-2 hover:bg-slate-50"
          >
            My Complaints
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto grid max-w-5xl gap-6 lg:grid-cols-[1.3fr_0.7fr]">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <p className="text-sm font-medium text-brand-600">Raise an issue</p>
      <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Submit a new complaint</h1>
      <p className="mt-2 text-sm text-slate-500">Give us enough detail so the right team can act quickly.</p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div>
          <label htmlFor="title" className="block text-sm font-medium text-slate-700">
            Title
          </label>
          <input
            id="title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Wi-Fi is not working in the hostel"
            className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
        </div>

        <div>
          <label htmlFor="description" className="block text-sm font-medium text-slate-700">
            Description
          </label>
          <textarea
            id="description"
            rows={5}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe what happened, where, and when..."
            className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
        </div>

        <div>
          <label htmlFor="peopleAffected" className="block text-sm font-medium text-slate-700">
            People Affected
          </label>
          <input
            id="peopleAffected"
            type="number"
            min={1}
            value={peopleAffected}
            onChange={(e) => setPeopleAffected(e.target.value)}
            className="mt-1 w-32 rounded-xl border border-slate-200 px-3 py-2.5 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
        </div>

        {error && (
          <p className="text-sm text-red-600" role="alert">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="w-full rounded-xl bg-brand-600 py-2.5 text-sm font-semibold text-white shadow-sm hover:-translate-y-0.5 hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isLoading ? "Submitting..." : "Submit Complaint"}
        </button>
      </form>
      </div>
      <aside className="h-fit rounded-2xl border border-brand-100 bg-brand-50 p-6">
        <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-white text-brand-600 shadow-sm">✦</div>
        <h2 className="font-semibold text-slate-900">AI-assisted resolution</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Samadhan Setu analyzes your complaint to suggest its category, priority, department, and possible duplicate reports.
        </p>
        <div className="mt-5 space-y-3 text-sm text-slate-600">
          <p>✓ Faster routing to the right department</p>
          <p>✓ Clear priority based on impact</p>
          <p>✓ Track progress from one place</p>
        </div>
      </aside>
    </div>
  );
}

export default NewComplaint;
