import client from "./client";
import type {
  JDCreateRequest,
  JDCreateResponse,
  JDParseResponse,
  PlatformLoginResponse,
  PlatformSearchRequest,
  PlatformSearchResponse,
} from "@/types/jd";

export interface JDListItem {
  id: number;
  title: string;
  company: string;
  source: string;
}

export async function listJDs(): Promise<{ data: JDListItem[] }> {
  return client.get("/jds/list");
}

export async function createJD(req: JDCreateRequest): Promise<JDCreateResponse> {
  return client.post("/jds", req);
}

export async function parseJD(jdId: number): Promise<JDParseResponse> {
  return client.post(`/jds/${jdId}/parse`);
}

export async function openLoginBrowser(platforms: string[]): Promise<PlatformLoginResponse> {
  return client.post("/jds/platforms/open-login-browser", { platforms }, { timeout: 180000 });
}

export async function saveLoginState(): Promise<PlatformLoginResponse> {
  return client.post("/jds/platforms/save-login-state", {}, { timeout: 60000 });
}

export async function searchJobsFromPlatforms(req: PlatformSearchRequest): Promise<PlatformSearchResponse> {
  return client.post("/jds/platforms/search", req, { timeout: 360000 });
}


export async function collectCurrentEdgePages(req: PlatformSearchRequest): Promise<PlatformSearchResponse> {
  return client.post("/jds/platforms/collect-current", req, { timeout: 180000 });
}

export async function closeJobBrowser(): Promise<PlatformLoginResponse> {
  return client.post("/jds/platforms/close-browser", {}, { timeout: 60000 });
}

export async function clearPlatformCache(): Promise<{ success: boolean; message: string }> {
  return client.post("/jds/platforms/clear-cache", {}, { timeout: 30000 });
}

export async function deleteJD(jdId: number): Promise<{ success: boolean; message?: string }> {
  return client.delete(`/jds/${jdId}`);
}
