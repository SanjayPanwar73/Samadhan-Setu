import { useEffect, useState } from "react";
import api from "../services/api";
import { getDisplayName, getRole } from "../utils/auth";

function Profile() {
  const [profile, setProfile] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api
      .get("/auth/me")
      .then((response) => {
        if (active) setProfile(response.data);
      })
      .catch((err) => {
        if (active) {
          setError(err.response?.data?.detail || "Could not load your profile.");
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (isLoading) {
    return <div className="rounded-lg bg-white p-6 text-center text-sm text-slate-500">Loading profile...</div>;
  }

  if (error) {
    return <div className="rounded-lg bg-white p-6 text-center text-sm text-red-600">{error}</div>;
  }

  const role = profile?.role || getRole();
  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-800">Profile</h1>
        <p className="mt-1 text-sm text-slate-500">Your Samadhan Setu account details.</p>
      </div>
      <div className="rounded-lg bg-white p-6 shadow">
        <div className="flex items-center gap-4 border-b border-slate-100 pb-5">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-slate-800 text-xl font-semibold text-white">
            {getDisplayName(profile).charAt(0).toUpperCase()}
          </div>
          <div>
            <h2 className="text-lg font-semibold text-slate-800">{getDisplayName(profile)}</h2>
            <p className="text-sm capitalize text-slate-500">{role} account</p>
          </div>
        </div>
        <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-slate-500">Full name</dt>
            <dd className="mt-1 font-medium text-slate-800">{profile?.name || "—"}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Email</dt>
            <dd className="mt-1 font-medium text-slate-800">{profile?.email || "—"}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Role</dt>
            <dd className="mt-1 font-medium capitalize text-slate-800">{role || "—"}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Account ID</dt>
            <dd className="mt-1 font-medium text-slate-800">{profile?.id ?? "—"}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}

export default Profile;
