import client from "./client";
import type {
  AnalysisRunRequest,
  AnalysisRunResponse,
  RewriteResponse,
  ReportResponse,
  InterviewQuestionsResponse,
} from "@/types/analysis";

export interface EvidenceItem {
  source: string;
  source_type:
    | "resume_project"
    | "resume_skill"
    | "resume_work_experience"
    | "resume_education"
    | "jd_requirement"
    | "jd_preferred"
    | "system_rule";
  field: string;
  confidence: number;
}

export interface BulletEvidence {
  rewritten_bullet: string;
  resume_evidence: EvidenceItem[];
  jd_evidence: EvidenceItem[];
  risk: "low" | "medium" | "high";
  fabrication_check: "passed" | "warning" | "failed";
  need_manual_confirm: boolean;
}

export interface RewriteStrategy {
  target_role: string;
  role_requirements: string[];
  evidence_summary: string[];
  section_order: string[];
  project_style: string;
  tech_stack_rules: string[];
  quantification_rules: string[];
  tone_rules: string[];
  omitted_or_compressed: string[];
}

export interface RewriteQualityGateItem {
  name: string;
  status: "passed" | "warning" | "failed";
  message: string;
}



export interface FullRewriteData {
  job_title: string;
  target_company: string;
  summary: string;
  sections: { title: string; content: string }[];
  highlights: string[];
  full_text: string;
  changes_summary: string;
  evidence_chain: BulletEvidence[];
  rewrite_strategy?: RewriteStrategy | null;
  quality_gate?: RewriteQualityGateItem[];
}

export interface FullRewriteResponse {
  success: boolean;
  data: FullRewriteData | null;
  message?: string;
}

export async function runAnalysis(req: AnalysisRunRequest): Promise<AnalysisRunResponse> {
  return client.post("/analysis/run", req);
}

export async function getAnalysis(taskId: number): Promise<AnalysisRunResponse> {
  return client.get(`/analysis/${taskId}`);
}

export async function getRewrites(taskId: number): Promise<RewriteResponse> {
  return client.post(`/analysis/${taskId}/rewrite`);
}

export async function getReport(taskId: number): Promise<ReportResponse> {
  return client.get(`/analysis/${taskId}/report`);
}

export async function getInterviewQuestions(taskId: number): Promise<InterviewQuestionsResponse> {
  return client.post(`/analysis/${taskId}/interview-questions`);
}

export async function generateFullRewrite(taskId: number): Promise<FullRewriteResponse> {
  return client.post(`/analysis/${taskId}/full-rewrite`);
}

export async function getFullRewrite(taskId: number): Promise<FullRewriteResponse> {
  return client.get(`/analysis/${taskId}/full-rewrite`);
}

export async function saveEditedRewrite(taskId: number, editedText: string): Promise<{ success: boolean }> {
  return client.put(`/analysis/${taskId}/full-rewrite`, { edited_text: editedText });
}

export function exportFullRewritePdfUrl(taskId: number): string {
  return `/api/v1/analysis/${taskId}/full-rewrite/export/pdf`;
}


export function exportFullRewriteWordUrl(taskId: number): string {
  return `/api/v1/analysis/${taskId}/full-rewrite/export/word`;
}

export async function deleteAnalysisTask(taskId: number): Promise<{ success: boolean; message?: string }> {
  return client.delete(`/analysis/${taskId}`);
}
