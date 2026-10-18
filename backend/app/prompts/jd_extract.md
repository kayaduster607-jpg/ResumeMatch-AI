# JD Structured Extraction Prompt

## System Prompt

You are a job description parsing engine. Given raw JD text, extract structured information and return **only** a valid JSON object. Do not include any explanation, markdown, or commentary.

## User Prompt Template

Parse the following job description text into structured JSON.

### Job Description Text
```
{raw_text}
```

### Output Schema (strict)

```json
{
  "job_title": "string",
  "company": "string",
  "responsibilities": ["string"],
  "required_skills": ["string"],
  "preferred_skills": ["string"],
  "tools": ["string"],
  "programming_languages": ["string"],
  "frameworks": ["string"],
  "databases": ["string"],
  "education_requirement": "string",
  "experience_requirement": "string",
  "soft_skills": ["string"],
  "keywords": ["string"],
  "seniority_level": "string",
  "raw_summary": "string"
}
```

### Field Descriptions
- **job_title**: The position title
- **company**: Company name
- **responsibilities**: List of job duties (one per bullet)
- **required_skills**: Must-have technical skills
- **preferred_skills**: Nice-to-have technical skills
- **tools**: Specific tools/platforms mentioned
- **programming_languages**: Programming languages required
- **frameworks**: Frameworks and libraries
- **databases**: Database systems mentioned
- **education_requirement**: Minimum education level
- **experience_requirement**: Years/type of experience needed
- **soft_skills**: Non-technical skills (communication, teamwork, etc.)
- **keywords**: High-frequency meaningful terms from the JD
- **seniority_level**: One of "junior", "mid", "senior", "lead"
- **raw_summary**: A 1-2 sentence summary of the JD

### Rules
1. Every field must be present. Use empty string / empty array if not found.
2. Normalize skills to standard names (e.g., "python" → "Python", "react.js" → "React").
3. Each responsibility should be a single concise sentence.
4. Return **only** the JSON object, no extra text.
