"""
Extraction Agent - Docling OCR + Claude Extraction

TWO-STEP PIPELINE:
1. Docling converts PDF → clean structured text (handles OCR, layout, tables)
2. Claude extracts fields from clean text (not raw pixels)

This separation of concerns fixes the KC ID extraction issue:
- Docling sees "987654321" as text in a table cell
- Claude sees "Student ID: 987654321" as plain text, not pixels

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

# Try to import Docling (optional dependency)
try:
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
    print("[Extraction] Docling available - using OCR preprocessing")
except ImportError:
    DOCLING_AVAILABLE = False
    print("[Extraction] Docling not installed - using Claude vision only")


def detect_workflow(filename: str) -> str:
    """Detect workflow type from filename."""
    name = filename.lower()

    # Priority order: CACFP > Roster > KinderConnect
    # This handles files like "kinderconnect_cacfp_REAL_MESSY.pdf" correctly
    if "cacfp" in name or "meal" in name:
        return "cacfp"
    elif "roster" in name or "enrollment" in name:
        return "roster"
    elif "kinderconnect" in name or "attendance" in name:
        return "kinderconnect"
    raise ValueError(f"Cannot detect workflow from filename: {filename}")


def preprocess_pdf_with_docling(file_path: Path) -> str:
    """
    Use Docling to convert PDF to structured markdown.
    This handles OCR, layout analysis, and table extraction.
    Returns clean text that Claude can parse reliably.
    """
    if not DOCLING_AVAILABLE:
        return None

    try:
        converter = DocumentConverter()
        result = converter.convert(str(file_path))

        # Get structured markdown with tables preserved
        markdown_text = result.document.export_to_markdown()

        print(f"[Docling] Extracted {len(markdown_text)} characters from PDF")
        print(f"[Docling DEBUG] First 500 characters:")
        print(f"{markdown_text[:500]}")
        return markdown_text
    except Exception as e:
        print(f"[Docling] Failed to process PDF: {e}")
        return None


async def extract_from_text(text_content: str, schema: str, label: str = "") -> list[dict]:
    """Single responsibility: extract records from clean text."""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": f"""Extract all student records from this childcare report.

<document>
{text_content}
</document>

Schema for each record:
{schema}

<output_rules>
- Return a VALID JSON array, one object per student
- No markdown, no preamble
- The year for all dates is 2026 unless explicitly specified otherwise.
- All dates YYYY-MM-DD
- kc_id is MANDATORY — never null, never "UNKNOWN"
- Each student has a DIFFERENT kc_id
- Missing non-ID fields use null
</output_rules>

<negative_examples>
WRONG: [{{"child_name": "Rodriguez, Emma", "kc_id": null}}]
RIGHT: [{{"child_name": "Rodriguez, Emma", "kc_id": "987654321"}}]
</negative_examples>"""
            },
            {"role": "assistant", "content": "["}
        ]
    )

    raw = response.content[0].text.strip()
    if not raw.startswith("["):
        raw = "[" + raw
    print(f"[DEBUG]{label} Raw output (first 500):\n{raw[:500]}")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        # Attempt to recover truncated JSON
        print(f"[WARNING]{label} JSON parse failed: {e}")
        print(f"[WARNING]{label} Last 200 chars: {raw[-200:]}")
        return []


def extract_table_from_docling(markdown: str) -> str:
    """
    Extract the student table from Docling markdown output.
    Handles multiple possible header formats.
    """
    # DEBUG: always print what Docling actually gave us
    print(f"[Docling DEBUG] Full output preview:\n{markdown[:1500]}\n---")

    lines = markdown.split('\n')

    # Flexible header detection — catch any of these
    HEADER_KEYWORDS = ['child name', 'student name', 'name', 'student', 'child']

    header_idx = None
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if '|' in line and any(kw in line_lower for kw in HEADER_KEYWORDS):
            header_idx = i
            print(f"[Docling] Found table header at line {i}: {line}")
            break

    if header_idx is None:
        print(f"[Docling WARNING] No table header found — sending full markdown to Claude")
        return markdown  # ← send everything, let Claude figure it out

    # Collect header + all data rows (skip separator lines like |---|)
    table_lines = [lines[header_idx]]
    for line in lines[header_idx + 1:]:
        if '|' in line and not set(line.replace('|', '').strip()) <= set('-: '):
            table_lines.append(line)

    result = '\n'.join(table_lines)
    print(f"[Docling] Extracted {len(table_lines) - 1} data rows")
    return result


def get_schema(workflow: str) -> str:
    """Get extraction schema for workflow type."""
    schemas = {
        "kinderconnect": """{
  "child_name": "string (Last, First format e.g. 'Rodriguez, Emma')",
  "kc_id": "string (REQUIRED - numeric ID that appears in the document for each student, often in a table column or near the student name. Look carefully at ALL text near the student's row. Example: '987654321'. This field must NEVER be null, None, or 'UNKNOWN' - the ID is always present somewhere in the document)",
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


async def extract(file_path: str, workflow: str = None) -> list[dict]:
    """
    Extract structured records from PDF or CSV using Claude multimodal.

    This is a single-turn LLM call - no agentic loop needed.
    Handles any agency format without brittle parsers.
    """
    path = Path(file_path)
    if not workflow:
        workflow = detect_workflow(path.name)
    schema = get_schema(workflow)

    if path.suffix == ".csv":
        # Read CSV as text
        content = path.read_text()

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[
                {
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
- No markdown fences, no preamble"""
                },
                {"role": "assistant", "content": "["}  # Prefill to force JSON
            ]
        )

        text = response.content[0].text.strip()
        if not text.startswith("["):
            text = "[" + text

        try:
            records = json.loads(text)
            print(f"[CSV Extraction] Extracted {len(records)} records from roster")
            return records
        except json.JSONDecodeError as e:
            print(f"[WARNING] Failed to parse JSON: {e}")
            print(f"[WARNING] First 500 chars: {text[:500]}")
            return []

    # PDF path
    preprocessed_text = preprocess_pdf_with_docling(path)

    if preprocessed_text:
        table_text = extract_table_from_docling(preprocessed_text)

        # Count data rows to decide batching
        data_rows = [l for l in table_text.split('\n')
                     if '|' in l and not set(l.replace('|','').strip()) <= set('-: ')]

        print(f"[Extraction] {len(data_rows)} rows to process")

        # Dynamic batch size based on workflow complexity
        # KinderConnect: daily_records array = ~400-500 chars per student
        # CACFP: daily_meals array = ~200-300 chars per student
        # Roster: flat structure = ~100-150 chars per student
        BATCH_SIZES = {
            "kinderconnect": 10,  # Heavy - 5 days × 4 fields per day
            "cacfp": 15,          # Medium - 5 days × 1-2 fields per day
            "roster": 25          # Light - flat record
        }
        BATCH_SIZE = BATCH_SIZES.get(workflow, 10)  # Default to 10 if unknown

        print(f"[Extraction] Using batch size of {BATCH_SIZE} for {workflow} workflow")

        if len(data_rows) > BATCH_SIZE:
            # Get header line
            header = next((l for l in table_text.split('\n') if '|' in l), "")
            all_records = []

            for i in range(0, len(data_rows), BATCH_SIZE):
                batch = data_rows[i:i + BATCH_SIZE]
                batch_text = header + '\n' + '\n'.join(batch)
                label = f" [Batch {i//BATCH_SIZE + 1}]"
                records = await extract_from_text(batch_text, schema, label)
                all_records.extend(records)
                print(f"[Extraction]{label} Got {len(records)} records")

            return all_records
        else:
            return await extract_from_text(table_text, schema)

    else:
        # Vision fallback
        print("[Extraction] Docling unavailable — using Claude vision")
        with open(path, "rb") as f:
            pdf_b64 = base64.standard_b64encode(f.read()).decode()

        response = client.messages.create(
            model="claude-opus-4-20250514",  # Vision needs Opus
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "document", "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64
                        }},
                        {"type": "text", "text": f"""Extract all student records.
Schema: {schema}
<output_rules>
- JSON array only, no markdown
- kc_id MANDATORY, never null
- Dates YYYY-MM-DD
</output_rules>"""}
                    ]
                },
                {"role": "assistant", "content": "["}
            ]
        )
        raw = response.content[0].text.strip()
        if not raw.startswith("["):
            raw = "[" + raw
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []
