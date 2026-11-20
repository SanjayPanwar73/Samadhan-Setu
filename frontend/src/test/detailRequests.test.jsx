import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import IssueDetail from "../pages/IssueDetail";
import TaskDetail from "../pages/TaskDetail";
import api from "../services/api";

vi.mock("../services/api", () => ({ default: { get: vi.fn() }, getApiError: () => "Request failed" }));
beforeEach(() => api.get.mockReset());

function open(path, route, page) {
  render(<MemoryRouter initialEntries={[path]}><Routes><Route path={route} element={page} /></Routes></MemoryRouter>);
}

it("loads resolution advice only when staff ask for it", async () => {
  api.get.mockResolvedValueOnce({ data: { title: "Cooler repair", status: "assigned", complaints: [], updates: [] } })
    .mockResolvedValueOnce({ data: { suggestion: "Inspect the filter." } });
  open("/tasks/4", "/tasks/:id", <TaskDetail />);
  const button = await screen.findByRole("button", { name: "Get suggested approach" });
  expect(api.get.mock.calls.map(([url]) => url)).toEqual(["/tasks/4"]);
  await userEvent.click(button);
  await screen.findByText("Inspect the filter.");
  expect(api.get.mock.calls[1][0]).toBe("/tasks/4/suggested-resolution");
});

it("loads issue history when its tab is opened", async () => {
  api.get.mockImplementation(async (url) => {
    if (url === "/issues/4") return { data: { id: 4, title: "Cooler repair", status: "assigned", flags: {} } };
    if (url === "/issues/4/history") return { data: [{ id: 1, action: "complaint_submitted" }] };
    return { data: [] };
  });
  open("/issues/4", "/issues/:id", <IssueDetail />);
  const tab = await screen.findByRole("tab", { name: "History" });
  const urls = () => api.get.mock.calls.map(([url]) => url);
  for (const suffix of ["history", "complaints", "assignments", "resolutions"])
    expect(urls()).not.toContain(`/issues/4/${suffix}`);
  await userEvent.click(tab);
  await screen.findByText("complaint submitted");
  expect(urls()).toContain("/issues/4/history");
});
