# Samadhan Setu frontend

The existing React application, redesigned around complaint resolution, role-based workspaces, and the existing FastAPI backend. It uses React 19, React Router, Vite, Tailwind CSS, and Axios. All displayed records and metrics come from the API; fixtures live only in automated tests.

## Run locally

Use Node.js 22.12+ (validated with Node 24).

```sh
cd frontend
npm ci
npm run dev
```

In Windows PowerShell, use `npm.cmd` if the local execution policy blocks `npm.ps1`.

Set `VITE_API_URL` in `frontend/.env` to the backend origin, for example:

```dotenv
VITE_API_URL=http://localhost:8000
```

`VITE_API_BASE_URL` remains supported as a fallback. The development default is `http://localhost:8000`. Start the backend separately using its README. No backend or database changes are required by this frontend update.

Public registration creates community accounts. Staff and management accounts are created by administrators. Development account shortcuts require both Vite development mode and `VITE_ENABLE_DEMO_ACCOUNTS=true`; they are excluded from production builds. Existing seeded accounts can still sign in normally.

## Checks

```sh
npm run test
npm run lint
npm run build
npm run format:check
npm run preview
```

Vitest and Testing Library run interaction tests in jsdom with mocked API responses. Tests cover session validation, rejected-session handling, safe redirects, role restrictions, StrictMode request deduplication, pagination, local filtering, submission payloads, on-demand resolution guidance, feedback reopening, assignment, and confirmation dialogs. No test writes to the real backend.

Browser-level layout checks and a live API smoke test are separate from these DOM tests. Native dialog focus trapping is provided by the browser and stubbed in jsdom.

## Application structure

- `src/App.jsx`: existing routes with lazy-loaded pages and role guards.
- `src/contexts/AuthContext.jsx`: one shared identity request, session expiry and cross-tab synchronization.
- `src/services/api.js`: authenticated Axios client, bounded timeouts, and normalized API errors.
- `src/hooks/`: abortable data requests, directory loading, and incremental complaint/activity pagination.
- `src/components/ui.jsx`: buttons, cards, fields, alerts, badges, skeletons, dialogs, and reusable page chrome.
- `src/components/UserLayout.jsx`: desktop navigation, mobile drawer, breadcrumbs, profile, and sign-out.
- `src/components/ComplaintWorkspace.jsx`: shared community/staff dashboard and filters.
- `src/components/ComplaintTable.jsx`: desktop table and mobile complaint cards.
- `src/components/DistributionChart.jsx`: accessible category bars with visible values, without a charting runtime.
- `src/index.css`: visual tokens, component styles, responsive layouts, and reduced-motion support.

## Routes

| Route                          | Access                                            |
| ------------------------------ | ------------------------------------------------- |
| `/login`, `/register`          | Public; signed-in users return to their workspace |
| `/complaints`                  | Community account                                 |
| `/complaints/new`              | Community account                                 |
| `/staff`                       | Staff                                             |
| `/admin`, `/admin/departments` | Administrator                                     |
| `/management`                  | Management and administrator                      |
| `/complaints/:id`              | Signed in; backend enforces complaint visibility  |
| `/profile`, `/notifications`   | All signed-in accounts                            |
| `/dashboard`, `/`              | Redirect to the account's workspace               |

Staff status actions and resolution guidance are shown only for assigned complaints. The backend remains the authority for authorization and business logic.

## Data and behavior

Complaint and activity lists fetch 25 records plus one lookahead record, then offer **Load more**. Search, filters, and summary cards explicitly describe their scope when only part of the dataset is loaded. Department and staff selectors load all available directory pages so records are not silently omitted.

Management volume and SLA metrics use their existing aggregation endpoints. Resolution bars show average days **by category**; they do not imply a time trend. The priority queue preserves the backend's grouped/bounded results. SLA breach counts retain the backend's pending/in-progress scope.

Resolution guidance is requested only on demand. Most requests time out after 60 seconds; complaint submission and guidance allow 120 seconds. Mutations are never automatically retried. Patch responses update the page directly; feedback refreshes details because it can reopen a complaint.

No unsupported profile editing, read/unread notification states, fabricated history, override provenance, or attachment upload has been added. Department/priority overrides preserve existing API semantics, including the inability to clear a department through that endpoint.

## Deploying the existing application

Build with the appropriate public `VITE_API_URL`, serve `dist/`, and configure the host to return `index.html` for client-side routes such as `/complaints/12`. Serve the application and API over HTTPS and allow the frontend origin in backend CORS settings. Do not put server secrets in `VITE_*` variables; they are part of the client bundle. JWT storage remains compatible with the existing backend.
