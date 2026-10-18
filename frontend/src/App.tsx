import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import AppLayout from "./components/Layout/AppLayout";
import LoadingSpinner from "./components/LoadingSpinner";

const HomePage = lazy(() => import("./pages/HomePage"));
const UploadResumePage = lazy(() => import("./pages/UploadResumePage"));
const JDInputPage = lazy(() => import("./pages/JDInputPage"));
const AnalysisPage = lazy(() => import("./pages/AnalysisPage"));
const ReportPage = lazy(() => import("./pages/ReportPage"));
const RewritePage = lazy(() => import("./pages/RewritePage"));
const InterviewPage = lazy(() => import("./pages/InterviewPage"));

function App() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<HomePage />} />
          <Route path="upload" element={<UploadResumePage />} />
          <Route path="jd" element={<JDInputPage />} />
          <Route path="analysis" element={<AnalysisPage />} />
          <Route path="report/:taskId" element={<ReportPage />} />
          <Route path="rewrite/:taskId" element={<RewritePage />} />
          <Route path="interview/:taskId" element={<InterviewPage />} />
          <Route path="interview" element={<InterviewPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}

export default App;
