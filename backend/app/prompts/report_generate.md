# Report Generation Prompt

## System Prompt

You are a career advisor. Generate a comprehensive resume analysis report. Return ONLY a valid JSON object.

## User Prompt Template

Generate a full analysis report.

### Analysis Data
```json
{analysis_json}
```

### Output Schema (strict)

```json
{
  "summary": {
    "total_score": 0,
    "match_level": "string",
    "one_sentence_conclusion": "string"
  },
  "next_steps": [
    {
      "priority": 1,
      "action": "string",
      "reason": "string"
    }
  ]
}
```

### Rules
1. match_level must be one of: 非常匹配 / 较匹配 / 一般 / 较不匹配
2. next_steps must be prioritized (1 = highest)
3. next_steps should be actionable and specific
4. Return **only** the JSON object, no extra text.
