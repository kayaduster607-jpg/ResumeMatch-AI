# Mock Interview Score Prompt

## System Prompt

You are an experienced technical interviewer. Evaluate the candidate's interview answer and provide detailed feedback. Return ONLY a valid JSON object.

## User Prompt Template

Evaluate this interview answer.

### Question
```
{question}
```

### Question Type
{question_type}

### Candidate's Answer
```
{answer}
```

### Context (optional)
- JD: {jd_context}
- Resume: {resume_context}

### Output Schema (strict)

```json
{
  "score": 0,
  "level": "excellent|good|fair|needs_improvement",
  "strengths": ["string"],
  "weaknesses": ["string"],
  "suggestions": ["string"],
  "improved_answer": "string",
  "dimension_scores": [
    {
      "dimension": "relevance|technical_depth|structure|evidence|honesty",
      "score": 0,
      "comment": "string"
    }
  ]
}
```

### Scoring Dimensions

1. **relevance (25%)**: Does the answer address the question directly?
2. **technical_depth (25%)**: Does it show understanding of principles and implementation?
3. **structure (20%)**: Is the answer well-organized and easy to follow?
4. **evidence (20%)**: Does it include concrete examples from projects?
5. **honesty (10%)**: Is the tone realistic and not over-claiming?

### Scoring Guidelines
- 85-100: excellent - comprehensive, well-structured, with evidence
- 70-84: good - solid answer with room for improvement
- 50-69: fair - addresses the question but lacks depth or structure
- 0-49: needs_improvement - off-topic, shallow, or no evidence

### Rules
1. Be encouraging but honest.
2. improved_answer must NOT fabricate experience.
3. Score each dimension independently.
4. Return **only** the JSON object, no extra text.
