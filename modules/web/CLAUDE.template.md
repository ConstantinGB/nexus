# {project_name} — Web

This project is a web development environment. It may be a frontend app, a full-stack
project, a static site, or a backend API. Read `package.json` (or equivalent) to determine
the exact stack and available scripts before making suggestions.

## Key software

- **Node.js** — runtime; check version via `.nvmrc` or `.node-version`; switch with `nvm use` or `fnm use`
- **Package managers** — check `package.json` for `packageManager` field; also look for `pnpm-lock.yaml`, `yarn.lock`, or `bun.lockb`
- **Vite** — most common build/dev tool: `vite dev` (port 5173), `vite build`, `vite preview`
- **Next.js** — React framework with SSR/SSG: `next dev` (port 3000), check `next.config.*`
- **TypeScript** — check `tsconfig.json`; run `tsc --noEmit` for type errors without emitting files
- **ESLint / Prettier** — linting and formatting; configs in `.eslintrc.*` or `eslint.config.*`
- **Vitest / Jest** — unit tests: `vitest`, `jest`
- **Playwright / Cypress** — end-to-end tests: `playwright test`, `cypress open`
- **Tailwind CSS** — check `tailwind.config.*`; use utility classes in markup, `@apply` in CSS

## Typical tasks

- Start the dev server and verify hot-reload is working
- Add or update components, pages, routes, and API endpoints
- Write and run unit and e2e tests; interpret test output
- Debug build errors: TypeScript type errors, missing imports, config issues
- Set up environment variables in `.env.local` (never commit real secrets)
- Optimise bundle size: analyse with `vite-bundle-visualizer` or `@next/bundle-analyzer`
- Add dependencies: use the correct package manager (`pnpm add`, `npm install`, `bun add`)

## File and config conventions

- **`package.json → scripts`** — source of truth for available commands
- **`.env.local`** / **`.env`** — environment variables; `.env.example` shows required keys
- **`src/`** or **`app/`** — main source directory (varies by framework)
- **`public/`** — static assets served as-is
- **`dist/`** or **`.next/`** or **`build/`** — build output (git-ignored)
- **`node_modules/`** — dependencies (git-ignored; never edit directly)

---

## Your setup

<!-- Framework and version:
     e.g. Next.js 15, SvelteKit 2, Astro 4, vanilla + Vite, Express + Node 22 -->

<!-- Package manager: npm / pnpm / yarn / bun -->

<!-- Project root path:
     e.g. ~/projects/my-site -->

<!-- Dev server URL:
     e.g. http://localhost:5173, http://localhost:3000 -->

<!-- Test runner: Vitest / Jest / Playwright / none -->

<!-- Deployment target:
     e.g. Vercel, Cloudflare Pages, VPS with nginx, Docker container -->

## Skills

| Skill | Inputs | Description |
|-------|--------|-------------|
| `web_list_scripts` | `project_slug` | List all scripts from package.json |
| `web_run_script` | `project_slug`, `script` | Run a named package.json script |

## Local Model Guidance

Both skills are mechanical calls. Reliable with any model.

- Use `web_list_scripts` to give the AI context before asking which script to run.
- For code generation (components, hooks, API routes), paste the relevant existing code and ask a specific question. Local 7B+ models handle React/Vue/Svelte component generation well with explicit context.
- Prompt style: include the framework name and TypeScript/JavaScript distinction in every prompt.
- If the model returns no tool call: re-prompt with "Call web_list_scripts with project_slug: X."

## Notes for the AI

<!-- Any specific conventions: component naming, folder structure rules,
     state management library (Zustand, Pinia, Redux), CSS approach. -->
