import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { BandBadge, IssueFlags, IssueStatusBadge, PriorityBreakdown, SlaIndicator } from "../components/IssueParts";
import Timeline from "../components/Timeline";
import { DEFAULT_REQUIRED, requiredFields, validateResolution } from "../components/ResolutionForm";
import { bandsProblem, weightsProblem } from "../pages/SuperConfig";
import { membershipProblem } from "../pages/SuperUsers";
import { formatDuration, minutesUntil, newRequestId, reasonCodeLabel, toQuery } from "../utils/issues";

const html = (node) => renderToStaticMarkup(node);

describe("issue helpers", () => {
  it("builds query strings without empty values", () => {
    expect(toQuery({ status: "open", q: "", band: undefined, escalated: false, offset: 0 })).toBe("?status=open&offset=0");
    expect(toQuery({})).toBe("");
  });
  it("creates a distinct request id per call", () => {
    const ids = new Set(Array.from({ length: 20 }, newRequestId));
    expect(ids.size).toBe(20);
    expect([...ids][0].length).toBeGreaterThanOrEqual(8);
  });
  it("describes reason codes for humans", () => {
    expect(reasonCodeLabel("SAFETY_RULE:ELECTRICAL_HAZARD")).toBe("Safety rule: electrical hazard");
    expect(reasonCodeLabel("RECURRENCE_2_IN_90D")).toContain("2 earlier issue(s)");
    expect(reasonCodeLabel("VOLUME_SATURATED")).toBe("Report volume saturated");
    expect(reasonCodeLabel("SOMETHING_NEW")).toBe("SOMETHING_NEW");
  });
  it("formats time left and overdue", () => {
    const now = Date.parse("2026-11-12T10:00:00Z");
    expect(minutesUntil("2026-11-12T11:30:00Z", now)).toBe(90);
    expect(minutesUntil("2026-11-12T09:00:00Z", now)).toBe(-60);
    expect(minutesUntil(null, now)).toBeNull();
    expect(formatDuration(45)).toBe("45 min");
    expect(formatDuration(-180)).toBe("3 h");
    expect(formatDuration(60 * 24 * 5)).toBe("5 d");
  });
});

describe("issue components", () => {
  it("shows priority band and score, or a neutral badge when unrated", () => {
    expect(html(<BandBadge band="critical" score={82.4} />)).toContain("critical");
    expect(html(<BandBadge band="critical" score={82.4} />)).toContain("82");
    expect(html(<BandBadge />)).toContain("Unrated");
  });
  it("flags duplicates, recurrence and dissent for admins", () => {
    const out = html(<IssueFlags flags={{ possible_duplicate: true, recurrence: true, dissent: true, needs_review: true }} />);
    expect(out).toContain("Possible duplicate");
    expect(out).toContain("Recurrence");
    expect(out).toContain("Dissent");
    expect(html(<IssueFlags flags={{ needs_review: true, review_reason: "unclassified_triage" }} />)).toContain("Unclassified (Triage)");
    expect(html(<IssueFlags flags={{}} />)).toBe("");
  });
  it("labels statuses", () => {
    expect(html(<IssueStatusBadge status="awaiting_verification" />)).toContain("Awaiting verification");
  });
  it("shows SLA time left, overdue, and nothing for closed work", () => {
    const now = Date.parse("2026-11-12T10:00:00Z");
    expect(html(<SlaIndicator due="2026-11-12T12:00:00Z" now={now} />)).toContain("2 h left");
    const late = html(<SlaIndicator due="2026-11-12T08:00:00Z" now={now} />);
    expect(late).toContain("2 h overdue");
    expect(late).toContain("text-red-700");
    expect(html(<SlaIndicator due="2026-11-12T08:00:00Z" active={false} now={now} />)).toContain("—");
  });
  it("explains a stored priority assessment with factors and reason codes", () => {
    const assessment = {
      score: 80, band: "critical", algorithm_version: "priority-v2.0", config_version: "default",
      factors: {
        severity: { value: 1, weight: 0.2, contribution: 20 },
        safety: { value: 1, weight: 0.2, contribution: 20 },
        _meta: { raw_score: 45, safety_floor: 80 },
      },
      reason_codes: ["SAFETY_FLOOR_APPLIED", "SAFETY_RULE:ELECTRICAL_HAZARD"],
    };
    const out = html(<PriorityBreakdown assessment={assessment} />);
    expect(out).toContain("Safety / health risk");
    expect(out).toContain("Safety floor applied");
    expect(out).toContain("priority-v2.0");
    expect(out).not.toContain("raw_score");
    expect(html(<PriorityBreakdown assessment={null} />)).toContain("No assessment yet");
  });
  it("renders a timeline and an empty state", () => {
    expect(html(<Timeline events={[{ at: "2026-11-12T10:00:00Z", label: "Complaint received" }]} />)).toContain("Complaint received");
    expect(html(<Timeline events={[]} />)).toContain("No updates yet");
  });
});

describe("form rules mirror the backend", () => {
  it("resolution schema decides the required fields", () => {
    expect(requiredFields(undefined)).toEqual(DEFAULT_REQUIRED);
    expect(requiredFields({ required: ["action_taken"] })).toEqual(["action_taken"]);
    expect(Object.keys(validateResolution({ action_taken: "  " }, ["action_taken", "public_summary"]))).toEqual(["action_taken", "public_summary"]);
    expect(validateResolution({ action_taken: "Replaced fuse" }, ["action_taken"])).toEqual({});
  });
  it("priority weights must add up to one and bands must descend", () => {
    expect(weightsProblem({ a: 0.5, b: 0.5 })).toBe("");
    expect(weightsProblem({ a: 0.5, b: 0.4 })).toContain("add up to 1.00");
    expect(weightsProblem({ a: 1.5, b: -0.5 })).toContain("zero or more");
    expect(bandsProblem({ critical: 80, high: 60, medium: 30, low: 0 })).toBe("");
    expect(bandsProblem({ critical: 60, high: 60, medium: 30, low: 0 })).not.toBe("");
    expect(bandsProblem({ critical: 120, high: 60, medium: 30, low: 0 })).not.toBe("");
  });
  it("department membership follows the role", () => {
    expect(membershipProblem("staff", [1])).toBe("");
    expect(membershipProblem("staff", [1, 2])).not.toBe("");
    expect(membershipProblem("dept_admin", [])).not.toBe("");
    expect(membershipProblem("hod", [1, 2])).toBe("");
    expect(membershipProblem("hod", [])).not.toBe("");
    expect(membershipProblem("student", [1])).not.toBe("");
    expect(membershipProblem("super_admin", [])).toBe("");
  });
});
