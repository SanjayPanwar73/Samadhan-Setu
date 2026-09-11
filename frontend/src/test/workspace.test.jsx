import { StrictMode } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import api from "../services/api";

vi.mock("../services/api", async (importOriginal) => {
  const original = await importOriginal();
  return {
    ...original,
    default: {
      get: vi.fn(),
      post: vi.fn(),
      patch: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
    },
  };
});

let sequence = 200;
let user;
let records;
let consoleErrors;
const token = (profile) =>
  `eyJhbGciOiJIUzI1NiJ9.${btoa(JSON.stringify({ sub: String(profile.id), role: profile.role, exp: Math.floor(Date.now() / 1000) + 3600 }))}.test-signature`;
const complaint = (id, extra = {}) => ({
  id,
  title: `Concern ${id}`,
  description: "A detailed concern for the assigned team.",
  category: "Infrastructure",
  priority_score: 55,
  status: "pending",
  department_id: 1,
  created_by: user.id,
  assigned_to: null,
  created_at: "2026-09-01T10:00:00Z",
  sla_deadline: null,
  escalation_level: 0,
  priority_breakdown: null,
  ...extra,
});
function open(path, role = "user") {
  user.role = role;
  localStorage.setItem("token", token(user));
  window.history.replaceState({}, "", path);
  return render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  user = {
    id: ++sequence,
    name: "Taylor Morgan",
    email: "taylor@example.test",
    role: "user",
  };
  records = [];
  consoleErrors = vi.spyOn(console, "error").mockImplementation(() => {});
  api.get.mockImplementation(async (url, config) => {
    if (url === "/auth/me") return { data: user };
    if (
      ["/complaints/me", "/complaints/assigned", "/admin/complaints"].includes(
        url,
      )
    ) {
      const offset = config?.params?.offset || 0;
      return {
        data: records.slice(offset, offset + (config?.params?.limit || 20)),
      };
    }
    if (/^\/complaints\/\d+$/.test(url))
      return {
        data:
          records.find((item) => item.id === Number(url.split("/").at(-1))) ||
          complaint(1),
      };
    if (url.endsWith("/suggested-resolution"))
      return { data: { generated: false, retrieved_cases: [] } };
    if (url === "/management/sla-violations")
      return { data: { sla_violations_count: 0 } };
    return { data: [] };
  });
  api.post.mockResolvedValue({ data: {} });
});
afterEach(() => {
  expect(consoleErrors.mock.calls).toEqual([]);
});

describe("workspace integration", () => {
  it("keeps private routes behind sign in and remembers their destination", async () => {
    window.history.replaceState({}, "", "/complaints/8");
    render(<App />);
    await screen.findByRole("heading", { name: /welcome back|sign in/i });
    expect(window.location.pathname).toBe("/login");
    expect(window.history.state.usr.from).toBe("/complaints/8");
    expect(api.get).not.toHaveBeenCalled();
  });

  it("loads identity and complaints once in StrictMode, and filters without new requests", async () => {
    records = [
      complaint(1, { title: "Broken reading room light" }),
      complaint(2, { title: "Water supply restored", status: "resolved" }),
    ];
    open("/complaints");
    await screen.findByRole("heading", { name: "Welcome back, Taylor." });
    await waitFor(() =>
      expect(
        screen.getAllByText("Broken reading room light").length,
      ).toBeGreaterThan(0),
    );
    expect(
      api.get.mock.calls.filter(([url]) => url === "/auth/me"),
    ).toHaveLength(1);
    expect(
      api.get.mock.calls.filter(([url]) => url === "/complaints/me"),
    ).toHaveLength(1);
    await userEvent.type(screen.getByRole("searchbox"), "no such concern");
    expect(
      screen.getByRole("heading", { name: "No matching complaints" }),
    ).toBeTruthy();
    expect(
      api.get.mock.calls.filter(([url]) => url === "/complaints/me"),
    ).toHaveLength(1);
    await userEvent.click(
      screen.getAllByRole("button", { name: "Clear filters", exact: true })[0],
    );
  });

  it("loads records beyond the backend default page without inventing total counts", async () => {
    records = Array.from({ length: 27 }, (_, index) => complaint(index + 1));
    open("/complaints");
    await screen.findByText("Complaints loaded");
    await userEvent.click(
      await screen.findByRole("button", { name: /load more/i }),
    );
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /load more/i })).toBeNull(),
    );
    expect(
      api.get.mock.calls.some(
        ([url, config]) =>
          url === "/complaints/me" &&
          config.params.offset === 25 &&
          config.params.limit === 26,
      ),
    ).toBe(true);
    expect(screen.getByText(/Showing 27 of 27 loaded complaints/)).toBeTruthy();
  });

  it("shows a recoverable error when the list request fails", async () => {
    api.get.mockImplementation(async (url) => {
      if (url === "/auth/me") return { data: user };
      throw { isAxiosError: true };
    });
    open("/complaints");
    await screen.findByRole("heading", { name: "We couldn’t load this" });
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
    expect(
      screen.queryByText("Total complaints").parentElement.textContent,
    ).not.toMatch(/Total complaints0/);
  });

  it("shares profile identity with the shell", async () => {
    open("/profile");
    await screen.findAllByText(user.email);
    expect(
      api.get.mock.calls.filter(([url]) => url === "/auth/me"),
    ).toHaveLength(1);
  });

  it("prevents a community account from entering administrator routes", async () => {
    open("/admin");
    await screen.findByRole("heading", {
      name: "This space needs different access.",
    });
    expect(api.get.mock.calls.some(([url]) => url.startsWith("/admin/"))).toBe(
      false,
    );
  });

  it("allows administrators to use the existing management analytics API", async () => {
    open("/management", "admin");
    await waitFor(() =>
      expect(
        api.get.mock.calls.some(
          ([url]) => url === "/management/category-distribution",
        ),
      ).toBe(true),
    );
    expect(window.location.pathname).toBe("/management");
  });

  it("does not offer mutation or AI suggestion controls to an unassigned staff member", async () => {
    records = [complaint(5, { assigned_to: 999 })];
    open("/complaints/5", "staff");
    await screen.findByRole("heading", { name: "Concern 5" });
    expect(
      screen.queryByRole("button", {
        name: /mark in progress|start progress|generate|find similar|suggested resolution/i,
      }),
    ).toBeNull();
    expect(
      api.get.mock.calls.some(([url]) => url.endsWith("/suggested-resolution")),
    ).toBe(false);
  });

  it("provides a useful not-found route with a working return link", async () => {
    open("/this-route-does-not-exist");
    await screen.findByRole("heading", {
      name: "This page has taken a different path.",
    });
    expect(
      screen
        .getByRole("link", { name: /back to workspace/i })
        .getAttribute("href"),
    ).toBe("/complaints");
  });

  it("preserves the intended complaint destination after a successful login", async () => {
    window.history.replaceState({}, "", "/complaints/8");
    api.post.mockResolvedValue({
      data: { access_token: token(user), role: user.role, user },
    });
    render(<App />);
    await screen.findByRole("button", { name: "Sign in", exact: true });
    await userEvent.type(
      screen.getByLabelText("Email address"),
      "taylor@example.test",
    );
    await userEvent.type(
      screen.getByLabelText("Password", { exact: true }),
      "password123",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Sign in", exact: true }),
    );
    await waitFor(() => expect(window.location.pathname).toBe("/complaints/8"));
    expect(api.post).toHaveBeenCalledWith("/auth/login", {
      email: "taylor@example.test",
      password: "password123",
    });
    expect(
      api.get.mock.calls.filter(([url]) => url === "/auth/me"),
    ).toHaveLength(0);
  });

  it("sends trimmed complaint fields and the actual number affected", async () => {
    open("/complaints/new");
    await screen.findByRole("heading", { name: "Let’s get it resolved." });
    await userEvent.type(
      screen.getByLabelText("What’s the concern?"),
      "  Broken water pipe  ",
    );
    await userEvent.type(
      screen.getByLabelText("Tell us more"),
      "  Water has been leaking in the east hallway since Monday.  ",
    );
    const people = screen.getByLabelText("How many people are affected?");
    await userEvent.clear(people);
    await userEvent.type(people, "12");
    api.post.mockResolvedValue({
      data: complaint(99, { title: "Broken water pipe" }),
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Submit complaint" }),
    );
    await screen.findByRole("heading", {
      name: "Complaint submitted successfully.",
    });
    expect(api.post).toHaveBeenCalledWith(
      "/complaints",
      {
        title: "Broken water pipe",
        description: "Water has been leaking in the east hallway since Monday.",
        people_affected: 12,
      },
      { timeout: 120000 },
    );
    expect(
      screen
        .getByRole("link", { name: /view complaint/i })
        .getAttribute("href"),
    ).toBe("/complaints/99");
  });

  it("loads guidance only when an assigned staff member asks for it", async () => {
    records = [complaint(9, { assigned_to: user.id })];
    open("/complaints/9", "staff");
    await screen.findByRole("heading", { name: "Concern 9" });
    expect(
      api.get.mock.calls.some(([url]) => url.endsWith("/suggested-resolution")),
    ).toBe(false);
    await userEvent.click(
      screen.getByRole("button", { name: "Find resolution guidance" }),
    );
    await screen.findByRole("heading", { name: "No similar resolutions yet" });
    expect(
      api.get.mock.calls.filter(([url]) =>
        url.endsWith("/suggested-resolution"),
      ),
    ).toHaveLength(1);
  });

  it("does not reject a complaint until the confirmation is submitted", async () => {
    records = [complaint(10, { assigned_to: user.id })];
    open("/complaints/10", "staff");
    await screen.findByRole("heading", { name: "Concern 10" });
    await userEvent.click(
      screen.getByRole("button", { name: "Reject complaint" }),
    );
    const dialog = await screen.findByRole("dialog");
    expect(api.patch).not.toHaveBeenCalled();
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Cancel" }),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    await userEvent.click(
      screen.getByRole("button", { name: "Reject complaint" }),
    );
    api.patch.mockResolvedValue({
      data: { ...records[0], status: "rejected" },
    });
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Confirm rejection",
      }),
    );
    await screen.findByText("Complaint marked rejected.");
    expect(api.patch).toHaveBeenCalledWith("/complaints/10/status", {
      status: "rejected",
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("keeps feedback confirmation visible when a low rating reopens the concern", async () => {
    records = [complaint(11, { status: "resolved" })];
    open("/complaints/11");
    await screen.findByRole("heading", { name: "Concern 11" });
    await userEvent.click(screen.getByRole("radio", { name: "1 out of 5" }));
    api.post.mockImplementation(async () => {
      records[0] = { ...records[0], status: "reopened" };
      return { data: { message: "Feedback recorded" } };
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Submit feedback" }),
    );
    await screen.findByText(
      "Thank you for your feedback. Your complaint has been reopened for another review.",
    );
    expect(api.post).toHaveBeenCalledWith("/complaints/11/feedback", {
      rating: 1,
      comment: null,
    });
    expect(
      screen.queryByRole("button", { name: "Submit feedback" }),
    ).toBeNull();
  });

  it("updates assignment and fetches fresh workload when opening the team panel", async () => {
    const normal = api.get.getMockImplementation();
    records = [complaint(12)];
    api.get.mockImplementation(async (url, config) =>
      url === "/admin/staff"
        ? {
            data: [
              {
                id: 500,
                name: "Case Worker",
                email: "worker@example.test",
                role: "staff",
                department_id: 1,
              },
            ],
          }
        : normal(url, config),
    );
    open("/admin", "admin");
    await screen.findByRole("heading", { name: "Keep every concern moving." });
    api.patch.mockResolvedValue({ data: { ...records[0], assigned_to: 500 } });
    await userEvent.selectOptions(
      (await screen.findAllByLabelText("Assign complaint 12"))[0],
      "500",
    );
    await screen.findByText("Assignment updated for complaint #12.");
    expect(api.patch).toHaveBeenCalledWith("/admin/complaints/12/assign", {
      staff_id: 500,
    });
    await userEvent.click(screen.getByRole("tab", { name: "Team & workload" }));
    await waitFor(() =>
      expect(
        api.get.mock.calls.some(([url]) => url === "/admin/staff-workload"),
      ).toBe(true),
    );
  });

  it("validates department deletion in a dialog before calling its API", async () => {
    const normal = api.get.getMockImplementation();
    api.get.mockImplementation(async (url, config) =>
      url === "/admin/departments"
        ? { data: [{ id: 3, name: "Facilities", category: "power,lighting" }] }
        : normal(url, config),
    );
    open("/admin/departments", "admin");
    await screen.findByText("Facilities");
    await userEvent.click(
      screen.getByRole("button", { name: "Delete Facilities" }),
    );
    expect(api.delete).not.toHaveBeenCalled();
    api.delete.mockResolvedValue({ data: { message: "Department deleted" } });
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Delete department",
      }),
    );
    await screen.findByText("Facilities has been deleted.");
    expect(api.delete).toHaveBeenCalledWith("/admin/departments/3");
  });
});
