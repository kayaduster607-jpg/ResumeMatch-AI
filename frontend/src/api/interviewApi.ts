import client from "./client";
import type { MockInterviewRequest, MockInterviewResponse } from "@/types/interview";

export interface InterviewStartRequest {
  task_id: number;
  use_rewritten_resume: boolean;
}

export interface InterviewStartData {
  task_id: number;
  jd_title: string;
  company: string;
  use_rewritten_resume: boolean;
  // The backend sets this flag for both model-driven and rule-based sessions.
  used_ai: boolean;
  tips: string[];
  first_question: string;
  focus_points: string[];
}

export interface InterviewChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface InterviewChatRequest {
  task_id: number;
  message: string;
  history: InterviewChatMessage[];
  use_rewritten_resume: boolean;
}

export interface InterviewChatData {
  assistant_message: string;
  feedback: string;
  next_question: string;
  tips: string[];
  score?: number;
}

export interface InterviewFinishRequest {
  task_id: number;
  history: InterviewChatMessage[];
  use_rewritten_resume: boolean;
}

export interface InterviewSummaryData {
  overall_score: number;
  overall_feedback: string;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  total_rounds: number;
}

export async function scoreAnswer(req: MockInterviewRequest): Promise<MockInterviewResponse> {
  return client.post("/interview/score", req);
}

export async function startInterview(req: InterviewStartRequest): Promise<{ success: boolean; data: InterviewStartData }> {
  return client.post("/interview/start", req, { timeout: 120000 });
}

export async function chatInterview(req: InterviewChatRequest): Promise<{ success: boolean; data: InterviewChatData }> {
  return client.post("/interview/chat", req, { timeout: 180000 });
}

export async function finishInterview(req: InterviewFinishRequest): Promise<{ success: boolean; data: InterviewSummaryData }> {
  return client.post("/interview/finish", req, { timeout: 180000 });
}
