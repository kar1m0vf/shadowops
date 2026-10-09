import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
// Separate entry modules keep live API hooks out of the public archive build.
const App = lazy(() => import.meta.env.MODE === "demo"
  ? import("./demo/ArchivedDemo")
  : import("./App"));
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Suspense fallback={<p role="status">Loading ShadowOps…</p>}><App /></Suspense>
  </StrictMode>,
);
