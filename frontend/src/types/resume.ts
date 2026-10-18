export interface ResumeUploadResponse {
  success: boolean;
  data: {
    resume_id: number;
    filename: string;
    text_preview: string;
  };
}

export interface ParsedResume {
  basic_info: {
    name: string;
    phone: string;
    email: string;
    gender: string;
    age: string;
    location: string;
    job_title: string;
    years_of_experience: string;
  };
  education: {
    school: string;
    degree: string;
    major: string;
    start_date: string;
    end_date: string;
    gpa: string;
  }[];
  work_experience: {
    company: string;
    title: string;
    start_date: string;
    end_date: string;
    description: string;
    achievements: string[];
  }[];
  projects: {
    name: string;
    role: string;
    start_date: string;
    end_date: string;
    tech_stack: string[];
    description: string;
    achievements: string[];
  }[];
  skills: string[];
  certificates: { name: string; issuer: string; date: string }[];
  awards: { name: string; date: string }[];
  self_evaluation: string;
  raw_quality_check: {
    is_too_short: boolean;
    missing_projects: boolean;
    missing_skills: boolean;
    missing_work_experience: boolean;
    issues: string[];
  };
}

export interface ResumeParseResponse {
  success: boolean;
  data: {
    resume_id: number;
    parsed_json: ParsedResume;
  };
}
