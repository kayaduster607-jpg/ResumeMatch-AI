export interface JDCreateRequest {
  title: string;
  company?: string;
  raw_text: string;
}

export interface JDCreateResponse {
  success: boolean;
  data: { jd_id: number };
}

export interface ParsedJD {
  job_title: string;
  company: string;
  responsibilities: string[];
  required_skills: string[];
  preferred_skills: string[];
  tools: string[];
  programming_languages: string[];
  frameworks: string[];
  databases: string[];
  education_requirement: string;
  experience_requirement: string;
  soft_skills: string[];
  keywords: string[];
  seniority_level: string;
  raw_summary: string;
}

export interface JDParseResponse {
  success: boolean;
  data: {
    jd_id: number;
    parsed_json: ParsedJD;
  };
}

export interface PlatformSearchRequest {
  keyword: string;
  city: string;
  platforms: string[];
  pages?: number;
  min_score?: number;
  top?: number;
  strict_city?: boolean;
  resume_id?: number | null;
  timeout_ms?: number;
  render_wait_ms?: number;
  job_type?: string;
  experience?: string;
  education?: string;
  district?: string;
  force_refresh?: boolean;  // 强制重新爬取，忽略缓存
}

export interface PlatformJobItem {
  id: string;
  platform: string;
  platform_name: string;
  title: string;
  company: string;
  city: string;
  district: string;
  address: string;
  salary: string;
  experience: string;
  education: string;
  detail_url: string;
  raw_text: string;
  source: string;
  match_score: number;
  match_level: string;
  recommendation: string;
  matched_skills: string[];
  missing_skills: string[];
  score_reason: string;
}

export interface PlatformSearchResponse {
  success: boolean;
  data: {
    keyword: string;
    city: string;
    platforms: string[];
    total_found: number;
    total_after_filter: number;
    jobs: PlatformJobItem[];
    errors: { platform?: string; platform_name?: string; message: string }[];
    elapsed_seconds: number;
    message: string;
    from_cache?: boolean;
  };
}

export interface PlatformLoginResponse {
  success: boolean;
  data: {
    message: string;
    profile_dir?: string;
    state_path?: string;
    opened?: { platform: string; url: string }[];
  };
}
