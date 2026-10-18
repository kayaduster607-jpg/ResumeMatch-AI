import client from "./client";
import type { ResumeUploadResponse, ResumeParseResponse } from "@/types/resume";

export interface ResumeListItem {
  id: number;
  filename: string;
  text_preview: string;
}

export async function listResumes(): Promise<{ data: ResumeListItem[] }> {
  return client.get("/resumes/list");
}

export async function uploadResume(file: File): Promise<ResumeUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return client.post("/resumes/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120000,
  });
}

export async function parseResume(resumeId: number): Promise<ResumeParseResponse> {
  return client.post(`/resumes/${resumeId}/parse`);
}

export async function deleteResume(resumeId: number): Promise<{ success: boolean; message?: string }> {
  return client.delete(`/resumes/${resumeId}`);
}
