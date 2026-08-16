/**
 * Whether the documentation section is part of this build.
 *
 * On by default in development, and off in a production build unless `VITE_SHOW_DOCS=true` is set
 * when the bundle is compiled. The flag exists because a hosted demo of a portfolio project is one
 * of the few cases where publishing its own documentation is the point — but that has to be a
 * deliberate choice per build, not the default.
 *
 * **`App.tsx` deliberately does not import this constant.** Rollup folds an `import.meta.env`
 * literal in place, but would not fold this imported binding early enough to remove the dynamic
 * `import()` behind it — which left the whole 62 KB docs chunk on disk even with the flag off. The
 * route gate therefore repeats the expression inline; this constant is for the cheap checks like
 * the nav entry. Do not "tidy" the duplication away without re-checking the built bundle.
 *
 * **This is a build-time flag, not a runtime one.** Vite substitutes both values as literals during
 * compilation, so with the flag unset the whole expression folds to `false`, Rollup eliminates every
 * branch guarded by it, and the docs chunk is never emitted. Setting it in the container's
 * environment at *run* time does nothing — it has to be passed as a build argument, which is why
 * `frontend/Dockerfile` declares `ARG VITE_SHOW_DOCS`.
 */
export const DOCS_ENABLED = import.meta.env.DEV || import.meta.env.VITE_SHOW_DOCS === "true";
