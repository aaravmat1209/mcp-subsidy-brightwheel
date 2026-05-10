"""
Extraction Agent - Claude Multimodal

Handles unstructured input (PDF/CSV) → structured JSON.
This is where LLMs add unique value - no deterministic parser can do this.

PRODUCTION SWAP:
- Use boto3 + Bedrock endpoint instead of Anthropic SDK
- Add retry logic for transient failures
- Stream large files from S3 instead of local reads
"""

import anthropic
import base64
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Anthropic client
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def detect_workflow(filename: str) -> str:
    """Detect workflow type from filename."""
    name = filename.lower()
    if "kinderconnect" in name or "attendance" in name:
        return "kinderconnect"
    elif "cacfp" in name or "meal" in name:
        return "cacfp"
    elif "roster" in name or "enrollment" in name:
        return "roster"
    raise ValueError(f"Cannot detect workflow from filename: {filename}")


def get_schema(workflow: str) -> str:
    """Get extraction schema for workflow type."""
    schemas = {
        "kinderconnect": """{
  "child_name": "string",
  "kc_id": "string (KinderConnect case ID)",
  "apt_type": "string (Full-Time or Part-Time)",
  "has_signature": "boolean",
  "daily_records": [
    {
      "date": "YYYY-MM-DD",
      "status": "P (Present) | AB (Absent) | OD (Off Day)",
      "in_time": "HH:MM (24-hour format)",
      "out_time": "HH:MM (24-hour format)"
    }
  ]
}""",
        "cacfp": """{
  "child_name": "string",
  "frp_category": "Free | Reduced | Paid",
  "daily_meals": [
    {
      "date": "YYYY-MM-DD",
      "meals": ["B", "AM", "L", "P", "S", "E"]
    }
  ],
  "non_payable_flags": ["string (reason if any)"]
}

Meal codes: B=Breakfast, AM=AM Snack, L=Lunch, P=PM Snack, S=Supper, E=Evening Snack""",
        "roster": """{
  "first_name": "string",
  "last_name": "string",
  "dob": "string (any date format)",
  "status": "string (enrollment status)",
  "homeroom": "string",
  "parent_name": "string",
  "parent_email": "string",
  "parent_phone": "string",
  "allergies": ["string"],
  "frp_category": "string",
  "issues_found": ["string (data quality issues)"]
}"""
    }
    return schemas[workflow]


async def extract(file_path: str) -> list[dict]:
    """
    Extract structured records from PDF or CSV using Claude multimodal.

    This is a single-turn LLM call - no agentic loop needed.
    Handles any agency format without brittle parsers.
    """
    path = Path(file_path)
    workflow = detect_workflow(path.name)
    schema = get_schema(workflow)

    if path.suffix == ".pdf":
        # Read PDF as base64
        with open(path, "rb") as f:
            pdf_b64 = base64.standard_b64encode(f.read()).decode()

        # Single Claude call - no iteration needed
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": f"""Extract all records from this document into a JSON array.

Schema for each record:
{schema}

IMPORTANT:
- Return ONLY a valid JSON array, no markdown, no preamble
- Include every record you see
- For dates, use YYYY-MM-DD format
- For missing fields, use null (not empty string)

Return the JSON array now:"""
                    }
                ]
            }]
        )

        text = response.content[0].text.strip()

        # Handle markdown code blocks if Claude adds them
        if text.startswith("```"):
            # Strip markdown
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[WARNING] Failed to parse JSON: {e}")
            print(f"[WARNING] Raw response: {text[:200]}...")
            # Return empty list rather than crash
            return []

    elif path.suffix == ".csv":
        # Read CSV as text
        content = path.read_text()

        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"""This is a messy enrollment CSV. Normalize every row and flag data quality issues.

Schema for each record:
{schema}

CSV content:
{content}

IMPORTANT:
- Return ONLY a valid JSON array
- Normalize names to title case
- Flag issues in the issues_found array
- Include every row

Return the JSON array now:"""
            }]
        )

        text = response.content[0].text.strip()

        # Handle markdown code blocks
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[WARNING] Failed to parse JSON: {e}")
            return []
