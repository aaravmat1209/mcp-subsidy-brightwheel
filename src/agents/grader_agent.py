"""
Grader Agent - Claude Evaluator

Evaluates reconciliation result quality.
This is where LLMs add value - judging prose quality is genuinely subjective.

PRODUCTION SWAP:
- Use boto3 + Bedrock endpoint
"""

import anthropic
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


GRADING_RUBRIC = """
A high-quality reconciliation result must satisfy ALL of these:
1. Every input record has exactly one classification (no silent drops)
2. Every exception has a specific, human-readable reason (not just "error")
3. Match rate > 0 (agent isn't classifying everything as NOT_FOUND)
4. Duplicate entries are flagged explicitly, not silently merged
5. Summary totals equal sum of matched + exception counts
6. No record is classified MATCH if there's a known discrepancy

Score 0-10. Return JSON:
{
  "pass": bool,        // true if score >= 7
  "score": int,
  "issues": [str],     // specific problems found, empty if pass
  "feedback": str      // brief summary for humans
}
"""


async def grade(workflow: str, input_records: list, result: dict) -> dict:
    """
    Grade a reconciliation result using Claude.

    This is genuinely subjective - evaluating whether exception reasons
    are clear and actionable for human operators.
    """
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"""Grade this {workflow} reconciliation result against the rubric.

Rubric:
{GRADING_RUBRIC}

Input records ({len(input_records)} total):
{json.dumps(input_records[:3], indent=2)}
... (showing first 3 for brevity)

Result:
{json.dumps(result, indent=2)}

Return ONLY valid JSON matching the schema above. No preamble."""
        }]
    )

    text = response.content[0].text.strip()

    # Handle markdown
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Return a failing grade if we can't parse
        return {
            "pass": False,
            "score": 0,
            "issues": ["Failed to parse grader response"],
            "feedback": "Grader agent error"
        }
