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
  category_name: "Infrastructure",
  department_name: "Facilities",
  status: "open",
  status_label: "Received",
  feedback_state: "none",
  created_at: "2026-09-01T10:00:00Z",
  ...extra,
});
function mockRoutes(routes) {
  const fallback = api.get.getMockImplementation();
  api.get.mockImplementation((url, options) =>
    Object.hasOwn(routes, url) ? routes[url](options) : fallback(url, options),
  );
}

function open(path, role = "student") {
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
    if (url === "/complaints/me") {
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
    if (url === "/notifications/unread-count") return { data: { unread: 0 } };
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

  it("loads identity and the student's complaints once in StrictMode", async () => {
    records = [
      complaint(1, { title: "Broken reading room light" }),
      complaint(2, { title: "Water supply restored" }),
    ];
    open("/complaints");
    const light = await screen.findByRole("link", { name: "Broken reading room light" });
    expect(light.getAttribute("href")).toBe("/complaints/1");
    expect(screen.getByRole("link", { name: "Water supply restored" }).getAttribute("href")).toBe("/complaints/2");
    expect(api.get.mock.calls.filter(([url]) => url === "/auth/me")).toHaveLength(1);
    expect(api.get.mock.calls.filter(([url]) => url === "/complaints/me")).toHaveLength(1);
  });

  it("loads records beyond the backend default page without inventing total counts", async () => {
    records = Array.from({ length: 27 }, (_, index) => complaint(index + 1));
    open("/complaints");
    await screen.findByRole("link", { name: "Concern 25" });
    expect(screen.queryByRole("link", { name: "Concern 26" })).toBeNull();
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
    expect(screen.getAllByRole("link", { name: /^Concern \d+$/ })).toHaveLength(27);
    expect(screen.getByRole("link", { name: "Concern 27" }).getAttribute("href")).toBe("/complaints/27");
  });

  it("retries the complaint list after a failed request", async () => {
    const list = vi.fn()
      .mockRejectedValueOnce({ isAxiosError: true })
      .mockResolvedValue({ data: [complaint(3)] });
    mockRoutes({ "/complaints/me": list });
    open("/complaints");
    await screen.findByRole("heading", { name: "We couldn’t load this" });
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByRole("link", { name: "Concern 3" });
    expect(list).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("heading", { name: "We couldn’t load this" })).toBeNull();
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

  it("opens the department analytics available to a legacy administrator", async () => {
    mockRoutes({
      "/issues?offset=0&limit=25": () => ({ data: { items: [], total: 0 } }),
      "/reports/department-summary": () => ({ data: { avg_resolution_hours: 12.5 } }),
    });
    open("/management", "admin");
    await screen.findByText("12.5 h");
    expect(window.location.pathname).toBe("/department");
  });

  it("keeps the management overview usable when weekly trends need a retry", async () => {
    const trends = vi.fn().mockRejectedValueOnce({ isAxiosError: true })
      .mockResolvedValue({ data: [{ weeks_ago: 0, opened: 3, resolved: 1 }] });
    mockRoutes({
      "/reports/trends": trends,
      "/reports/department-summary": () => ({ data: { total_issues: 3, total_reports: 4, reopen_rate: 0 } }),
    });
    open("/management", "management");
    await screen.findByRole("heading", { name: "We couldn’t load this" });
    expect(window.location.pathname).toBe("/hod");
    expect(screen.getByText("4 reports")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText("This week");
    expect(trends).toHaveBeenCalledTimes(2);
  });

  it("keeps work and advice unavailable when the task API denies access", async () => {
    mockRoutes({ "/tasks/5": () => Promise.reject({ response: { status: 404, data: { detail: "Task not found" } } }) });
    open("/tasks/5", "staff");
    await screen.findByText("Task not found");
    expect(screen.queryByRole("button", { name: /acknowledge|start work|get suggested approach/i })).toBeNull();
    expect(api.get.mock.calls.some(([url]) => url.endsWith("/suggested-resolution"))).toBe(false);
    expect(api.post).not.toHaveBeenCalled();
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
    api.get.mockImplementation(async (url, config) => {
      if (url === "/auth/me") return { data: user };
      if (url === "/reference/departments") return { data: [{ id: 1, name: "Water" }] };
      if (url === "/reference/categories") return { data: [
        { id: 2, department_id: 1, name: "Leaks" }, { id: 3, department_id: 2, name: "Lighting" },
      ] };
      if (url === "/reference/locations" && !config?.params?.parent_id)
        return { data: [{ id: 4, name: "Main campus", kind: "campus" }] };
      return { data: [] };
    });
    open("/complaints/new", "student");
    await screen.findByRole("option", { name: "Lighting" });
    await userEvent.selectOptions(screen.getByLabelText("Department"), "1");
    expect(screen.queryByRole("option", { name: "Lighting" })).toBeNull();
    await userEvent.selectOptions(screen.getByLabelText("Category"), "2");
    await userEvent.selectOptions(screen.getByLabelText("Campus"), "4");
    expect(api.get.mock.calls.filter(([url]) => url === "/reference/categories")).toHaveLength(1);
    await userEvent.type(
      screen.getByLabelText("Title"),
      "  Broken water pipe  ",
    );
    await userEvent.type(
      screen.getByLabelText("Describe the problem"),
      "  Water has been leaking in the east hallway since Monday.  ",
    );
    const people = screen.getByLabelText(/How many people are affected/);
    await userEvent.clear(people);
    await userEvent.type(people, "12");
    api.post.mockResolvedValue({
      data: { complaint_id: 99, ticket_no: "WAT-001", status_label: "Received" },
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Submit complaint" }),
    );
    await screen.findByRole("heading", {
      name: "Complaint submitted",
    });
    expect(api.post).toHaveBeenCalledWith(
      "/complaints",
      {
        title: "Broken water pipe",
        description: "Water has been leaking in the east hallway since Monday.",
        people_affected: 12,
        location_id: 4, department_id: 1, category_id: 2,
        client_request_id: expect.any(String), is_anonymous: false,
      },
      { timeout: 120000 },
    );
    expect(
      screen
        .getByRole("link", { name: "Track this complaint" })
        .getAttribute("href"),
    ).toBe("/complaints/99");
  });

  it("loads guidance only when an assigned staff member asks for it", async () => {
    const advice = vi.fn(() => ({ data: { suggestion: null, similar: [] } }));
    mockRoutes({
      "/tasks/9": () => ({ data: { title: "Concern 9", status: "assigned", complaints: [], updates: [] } }),
      "/tasks/9/suggested-resolution": advice,
    });
    open("/tasks/9", "staff");
    await screen.findByRole("heading", { name: "Concern 9" });
    expect(advice).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Get suggested approach" }));
    await screen.findByText("No suggested approach is available.");
    expect(advice).toHaveBeenCalledTimes(1);
  });

  it("requires an explicit reason before a department admin can reject an issue", async () => {
    const issue = { id: 10, title: "Concern 10", status: "open", flags: {} };
    mockRoutes({ "/issues/10": () => ({ data: { ...issue } }) });
    api.post.mockImplementation(async () => {
      issue.status = "rejected";
      return { data: { ...issue } };
    });
    open("/department/issues/10", "dept_admin");
    const reject = await screen.findByRole("button", { name: "Reject as invalid" });
    const reason = screen.getByLabelText(/Reason \(required/);
    await userEvent.type(reason, "Test");
    expect(reject.disabled).toBe(true);
    await userEvent.click(reject);
    expect(api.post).not.toHaveBeenCalled();
    await userEvent.type(reason, " report only");
    await userEvent.click(reject);
    await screen.findByText("Issue rejected.");
    expect(api.post).toHaveBeenCalledWith("/issues/10/reject", { reason: "Test report only" });
    await waitFor(() => expect(screen.queryByRole("button", { name: "Reject as invalid" })).toBeNull());
  });

  it("keeps feedback confirmation visible when feedback reopens an issue", async () => {
    records = [complaint(11, { status: "resolved", status_label: "Resolved", feedback_state: "pending" })];
    open("/complaints/11");
    await userEvent.click(await screen.findByRole("radio", { name: "1" }));
    await userEvent.click(screen.getByRole("radio", { name: "No" }));
    await userEvent.click(screen.getByRole("checkbox", { name: /still unresolved/i }));
    api.post.mockImplementation(async () => {
      records[0] = { ...records[0], status: "reopened", status_label: "Reopened", feedback_state: "submitted" };
      return { data: { id: 42, recorded: true, dissent: true } };
    });
    await userEvent.click(screen.getByRole("button", { name: "Send feedback" }));
    await screen.findByText("Thanks, your feedback has been recorded.");
    expect(screen.getByText("Reopened")).toBeTruthy();
    expect(api.post).toHaveBeenCalledWith("/complaints/11/feedback", {
      rating: 1, comment: null, resolved_for_me: false, still_unresolved: true,
    });
    expect(screen.queryByRole("form", { name: "Resolution feedback" })).toBeNull();
  });

  it("refreshes assignments and staff workload after assigning an issue", async () => {
    const assignments = [];
    const staff = vi.fn(() => ({ data: [{ id: 500, name: "Case Worker", active_tasks: assignments.length }] }));
    mockRoutes({
      "/issues/12": () => ({ data: { id: 12, title: "Concern 12", status: "open", department_id: 1, flags: {} } }),
      "/issues/12/assignments": () => ({ data: [...assignments] }),
      "/department-staff?department_id=1": staff,
    });
    api.post.mockImplementation(async () => {
      assignments.push({ id: 14, staff_id: 500, status: "assigned", is_lead: true });
      return { data: [...assignments] };
    });
    open("/department/issues/12", "dept_admin");
    await userEvent.click(await screen.findByRole("tab", { name: "Work" }));
    await userEvent.click(await screen.findByRole("checkbox", { name: /Case Worker.*0 active/ }));
    await userEvent.click(screen.getByRole("button", { name: "Assign", exact: true }));
    await screen.findByRole("checkbox", { name: /Case Worker.*1 active/ });
    expect(within(screen.getByRole("list", { name: "Assignments" })).getByText("Case Worker")).toBeTruthy();
    expect(api.post).toHaveBeenCalledWith("/issues/12/assignments", { staff_ids: [500], task_description: null });
    expect(staff).toHaveBeenCalledTimes(2);
  });

  it("deactivates and reactivates a department while preserving its record", async () => {
    const dept = { id: 3, name: "Facilities", code: "FAC", is_active: true, is_system: false };
    mockRoutes({ "/admin/org/departments": () => ({ data: [{ ...dept }] }) });
    api.patch.mockImplementation(async (_url, changes) => {
      Object.assign(dept, changes);
      return { data: { ...dept } };
    });
    open("/super/departments", "super_admin");
    const departmentRow = () => within(screen.getByRole("row", { name: /Facilities/ }));
    await screen.findByText("Facilities");
    expect(api.patch).not.toHaveBeenCalled();
    await userEvent.click(departmentRow().getByRole("button", { name: "Deactivate" }));
    await screen.findByText("Inactive");
    expect(api.patch).toHaveBeenCalledWith("/admin/org/departments/3", { is_active: false });
    await userEvent.click(departmentRow().getByRole("button", { name: "Activate" }));
    await screen.findByText("Active");
    expect(api.patch).toHaveBeenCalledWith("/admin/org/departments/3", { is_active: true });
    expect(api.delete).not.toHaveBeenCalled();
  });
});
