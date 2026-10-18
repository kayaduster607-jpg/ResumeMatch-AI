export interface MockInterviewRequest {
  question: string;
  answer: string;
  question_type: string;
  jd_context?: string;
  resume_context?: string;
}

export interface DimensionScore {
  dimension: string;
  score: number;
  comment: string;
}

export interface MockInterviewResult {
  score: number;
  level: string;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  improved_answer: string;
  dimension_scores: DimensionScore[];
}

export interface MockInterviewResponse {
  success: boolean;
  data: MockInterviewResult;
}
