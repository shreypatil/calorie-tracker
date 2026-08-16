/**
 * The docs route tree, in one lazily-imported module.
 *
 * Everything the documentation needs is reachable only from here, and this module is imported
 * exclusively behind `import.meta.env.DEV`. Vite replaces that with `false` in a production build,
 * Rollup then eliminates the branch, the `import()` call disappears with it, and the chunk is never
 * emitted — so none of this code ships. The build is checked for that rather than trusted.
 */

import { Route } from "react-router-dom";

import { Architecture } from "./Architecture";
import { DocsLayout } from "./DocsLayout";
import { Endpoints } from "./Endpoints";
import { Features } from "./Features";
import { Requirements } from "./Requirements";
import { Tests } from "./Tests";

/**
 * Paths are relative, not absolute.
 *
 * These render inside a nested `<Routes>` mounted at `/docs/*`, so react-router matches them
 * against what is left after `/docs/`. Writing `path="/docs"` here matches nothing and renders a
 * blank page with no error — which is exactly what it did the first time.
 */
export function docsRoutes() {
  return (
    <Route path="/" element={<DocsLayout />}>
      <Route index element={<Requirements />} />
      <Route path="requirements" element={<Requirements />} />
      <Route path="endpoints" element={<Endpoints />} />
      <Route path="architecture" element={<Architecture />} />
      <Route path="features" element={<Features />} />
      <Route path="tests" element={<Tests />} />
    </Route>
  );
}
