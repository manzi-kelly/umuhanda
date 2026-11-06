# Umuhanda — Road Rules Online Examination Platform

Phases 01–02 of a student-facing online examination platform for road rules in
Rwanda. This project is **frontend-only**: it includes the public landing page,
validated student onboarding, payment/promo interface and a locked exam-entry shell.
No payment is processed, no promo is approved and no exam access is granted.

## Stack

- Next.js 16 (App Router, Turbopack)
- React 19
- TypeScript (strict)
- Tailwind CSS v4
- Lucide React icons
- Self-hosted Google fonts through `next/font`

## Run locally

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Scripts

| Command             | Purpose                                    |
| ------------------- | ------------------------------------------ |
| `npm run dev`       | Start the development server               |
| `npm run build`     | Create a production build                  |
| `npm run build:webpack` | Build with supported Webpack alternative |
| `npm run start`     | Serve the production build                 |
| `npm run lint`      | Run ESLint                                 |
| `npm run typecheck` | Run TypeScript without emitting files      |
| `npm test`         | Run onboarding/payment unit tests          |
| `npm run test:browser` | Test production in Chrome at three widths |

## Project structure

```text
src/
  app/
    layout.tsx          # Root layout, fonts, metadata, header/footer
    page.tsx            # Home page composition
    globals.css         # Tailwind v4 theme tokens and base styles
    icon.svg            # Brand icon placeholder
    tangira/
      page.tsx          # Student information and payment selection
    exam/
      page.tsx          # Always-locked examination entry shell
  components/
    layout/
      Header.tsx        # Sticky desktop header
      MobileNav.tsx     # Client-side accessible mobile disclosure menu
      Footer.tsx        # Footer with navigation and contact placeholder
    home/
      HeroSection.tsx
      ExamPreviewCard.tsx
      HowItWorks.tsx
      ExamRules.tsx
      PaymentInformation.tsx
      FinalCTA.tsx
    ui/
      ButtonLink.tsx    # Reusable CTA link with variants
      Container.tsx     # Shared page width and gutters
      Logo.tsx          # Brand/logo placeholder
      SectionHeading.tsx
  lib/
    navigation.ts       # Site identity, route table and shared navigation links
    constants.ts        # Site content, rules, payment and footer data
    cn.ts               # Small class-name helper
```

## Phase 01 scope

Implemented:

- Premium, responsive homepage in Kinyarwanda
- Sticky desktop header and accessible mobile menu
- Hero, how-it-works, examination rules, payment information and final CTA
- Intersection-free anchor navigation with sticky-header scroll offset
- `/tangira` coming-soon page that clearly states no payment or exam is active
- Reusable components, shared design tokens and typed content constants
- Semantic landmarks, skip link, visible focus states and reduced-motion support
- Static prerendering compatible with future FastAPI integration

Not implemented (future phases):

- Admin dashboard
- Real payment gateway or payment simulation
- Exam timer/engine
- PDF processing
- Authentication backend
- PostgreSQL integration

## Payment and CTA behavior

All "Tangira Ikizamini" CTAs link to `/tangira`. Valid names and Rwanda mobile
numbers advance to MTN MoMo, Airtel Money or promo selection. Editing returns to
the student form with entered details preserved in React memory. Leaving or
reloading the page clears the information. Payment and promo adapters return
VERIFICATION_UNAVAILABLE without network requests, references or approval.
The UI never asks for a PIN and never claims a successful transaction.
`/exam` always displays rules, an unverified-name placeholder and a disabled
confirmation button. Browser state and query parameters cannot authorize entry.

See [Phase 02 API contract](docs/phase02-api-contract.md) and
[implementation report](docs/phase02-report.md) for the proposed integration and validation results.
See [build recovery and browser verification](docs/phase02-verification.md) for the
latest acceptance decision and execution evidence.

## Validation

Run the checks with:

```bash
npm run lint
npm run typecheck
npm run build
npm test
npm run test:browser
```

The production build should prerender `/`, `/tangira` and `/exam`.
Browser tests require installed Google Chrome and a completed production build.
Playwright starts and stops a test server on `127.0.0.1:3100`; it does not reuse a
service on port 3000. Screenshots and JSON results are saved under `docs/evidence`.

Run builds and browser tests with normal local process/socket access. Codex's
restricted Windows environment denies Turbopack worker loopback connections with
`EACCES`; use its reviewed execution permission for these commands. No Windows
security protection needs changing. If Node reports certificate trust errors on
this managed machine, use its system CA store in that terminal:

```powershell
$env:NODE_USE_SYSTEM_CA = '1'
npm run build:webpack
```

TLS verification stays enabled. Turbopack remains the default build strategy;
Webpack uses the same Tailwind v4 PostCSS configuration.

## Admin foundation (Phase 04A)

The public routes retain their existing URLs. Admin login is at `/admin/login`;
protected dashboard and workspace routes require a backend-verified session.
Only the student count is implemented; financial and exam metrics are unavailable.

See [Phase 04A implementation and verification](docs/phase04a-admin-dashboard.md)
for setup, authentication contracts, evidence and limitations. Configure server-only
origins using the root `.env.example` and run the existing FastAPI service on port8000.
The local production-server override is permitted only when both origins are loopback.
Use HTTPS and remove that override for public deployment.

Create the first administrator yourself in an interactive terminal, using an explicit
name, email and a 15–256 character passphrase. No development administrator or default
password is supplied:

```powershell
Set-Location backend
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe scripts/bootstrap_admin.py --confirm-first-admin
```

`npm run test:browser:admin` starts a separate API against the existing test database,
creates a random temporary test administrator and removes its fixture afterward.
Run it after backend tests, never concurrently with tests that reset that database.
## PDF import (Phase 04B)

After installing the backend dependencies and running `alembic upgrade head`, start
FastAPI and the separate PDF worker from `backend`. Use the same configured database
and private storage for both processes.

```powershell
.venv/Scripts/python.exe scripts/pdf_worker.py
```

Sign in and open `/admin/pdf-uploads` to upload a source PDF and review unpublished
drafts. The worker can also drain the current queue and exit with `--once`.
See [the Phase 04B report](docs/phase04b-pdf-import.md) for supported layouts, evidence
rules, configuration and verification.

## Automatic exam bank

The PDF worker automatically validates source evidence and activates ready banks.
The default policy requires explicit difficulty metadata. Configure
`EXAM_SELECTION_POLICY=UNSTRATIFIED` on the worker when unstratified selection is intended.
The protected dashboard reports bank readiness. The timed exam starts with a verified entitlement. [Phase 04C report](docs/phase04c-automatic-exam-bank.md)


## Development payments and promo codes

The backend can issue single-exam grants from an administrator promo code
or a local synthetic payment. Mock payments are off by default. The Phase 04D
report describes configuration, settlement and security checks.
[Phase 04D report](docs/phase04d-mock-payments-promos.md)


## Timed examination

Students can confirm an exam from a verified grant and resume the same
attempt on refresh. PostgreSQL controls deadlines and finalization.
[Phase 04E report](docs/phase04e-timed-examination.md)
