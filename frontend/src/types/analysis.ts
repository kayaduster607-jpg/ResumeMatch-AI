export interface AnalysisRunRequest {
  resume_id: number;
  jd_id: number;
}

export interface ScoreDetail {
  skill_score: number;
  skill_reason: string;
  project_score: number;
  project_reason: string;
  semantic_score: number;
  semantic_reason: string;
  requirement_score: number;
  requirement_reason: string;
}

export interface DiagnosisIssue {
  type: string;
  severity: "high" | "medium" | "low";
  title: string;
  evidence: string;
  reason: string;
  suggestion: string;
  rewrite_example: string;
}

export interface SuggestionItem {
  category: string;
  suggestion: string;
}

export interface AIAnalysis {
  provider: string;
  model: string;
  used_ai: boolean;
  overall_conclusion: string;
  match_positioning: string;
  key_strengths: Array<Record<string, any>>;
  core_gaps: Array<Record<string, any>>;
  resume_rewrite_strategy: string[];
  interview_risks: string[];
  action_plan: Array<Record<string, any>>;
  questions_to_prepare: string[];
  raw?: Record<string, any>;
}

export interface AnalysisResultData {
  task_id: number;
  report_id: number;
  total_score: number;
  score_detail: ScoreDetail;
  matched_skills: string[];
  missing_skills: string[];
  problems: DiagnosisIssue[];
  suggestions: SuggestionItem[];
  ai_analysis: AIAnalysis;
}

export interface AnalysisRunResponse {
  success: boolean;
  data: AnalysisResultData;
}

export interface AnalysisHistoryItem {
  task_id: number;
  resume_id: number;
  jd_id: number;
  resume_filename: string;
  jd_title: string;
  jd_company: string;
  total_score: number;
  match_level: string;
  status: string;
  created_at: string;
}

export interface ProjectRewrite {
  project_name: string;
  original_text: string;
  problems: string[];
  rewritten_text: string;
  missing_info_to_add: string[];
}

export interface RewriteResponse {
  success: boolean;
  data: { rewrites: ProjectRewrite[] };
}

export interface NextStep {
  priority: number;
  action: string;
  reason: string;
}

export interface SkillAnalysis {
  matched_skills: string[];
  missing_skills: string[];
  recommended_skills_to_learn: string[];
}

export interface FullReport {
  summary: {
    total_score: number;
    match_level: string;
    one_sentence_conclusion: string;
  };
  score_detail: ScoreDetail;
  skill_analysis: SkillAnalysis;
  resume_problems: DiagnosisIssue[];
  rewrite_suggestions: {
    project_name: string;
    original_text: string;
    rewritten_text: string;
    missing_info_to_add: string[];
  }[];
  interview_questions: InterviewQuestionItem[];
  next_steps: NextStep[];
  markdown_export: string;
}

export interface ReportResponse {
  success: boolean;
  data: FullReport;
}

export interface InterviewQuestionItem {
  question_type: string;
  difficulty: string;
  question: string;
  why_ask: string;
  reference_answer: string;
  related_resume_evidence: string;
  related_jd_requirement: string;
}

export interface InterviewQuestionsResponse {
  success: boolean;
  data: { questions: InterviewQuestionItem[] };
}
