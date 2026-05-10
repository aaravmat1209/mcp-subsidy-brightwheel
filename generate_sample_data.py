"""
Generate realistic sample data for Brightwheel reconciliation demo.

Creates:
1. KinderConnect attendance report (PDF) - Texas format
2. CACFP meal count report (PDF) - Federal format
3. Messy roster upload (CSV) - Tests data normalization

All field structures from official Brightwheel documentation.
"""

import json
import csv
from pathlib import Path
from datetime import date
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER


# ============================================================================
# 1. KINDERCONNECT ATTENDANCE REPORT
# ============================================================================

def generate_kinderconnect_report():
    """
    Creates a Texas KinderConnect Provider Attendance Summary.

    Fields from: https://help.mybrightwheel.com/en/articles/7157785

    Includes deliberate mismatches:
    - Child marked P (Present) but authorization expired (should be OD)
    - In/Out times don't match Brightwheel check-in
    - Missing parent signature
    """
    output_path = Path("data/kinderconnect_report.pdf")
    output_path.parent.mkdir(exist_ok=True)

    doc = SimpleDocTemplate(str(output_path), pagesize=landscape(letter),
                           topMargin=0.5*inch, bottomMargin=0.5*inch)

    story = []
    styles = getSampleStyleSheet()

    # Header
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#003366'),
        alignment=TA_CENTER,
        spaceAfter=6
    )

    story.append(Paragraph("KinderConnect Provider Attendance Summary", header_style))
    story.append(Paragraph("Week of May 5-9, 2026", ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, spaceAfter=12)))
    story.append(Spacer(1, 0.2*inch))

    # Provider info
    info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=9)
    story.append(Paragraph("<b>Provider ID:</b> TX-12345-CC | <b>Center:</b> Little Stars Academy", info_style))
    story.append(Spacer(1, 0.2*inch))

    # Attendance table
    data = [
        ['Child Name', 'KinderConnect ID', 'Mon 5/5', 'Tue 5/6', 'Wed 5/7', 'Thu 5/8', 'Fri 5/9', 'APT Type', 'Signature']
    ]

    # Student records with deliberate test cases
    students = [
        # Perfect matches
        ("Rodriguez, Emma", "987654321", "P\n7:15-4:30", "P\n7:20-4:15", "P\n7:10-4:45", "P\n7:25-4:20", "P\n7:15-4:30", "Full-Time", "✓"),
        ("Chen, Liam", "987654322", "P\n8:00-5:00", "P\n8:05-5:05", "P\n8:00-5:00", "P\n7:55-5:10", "P\n8:00-5:00", "Full-Time", "✓"),
        ("Patel, Olivia", "987654323", "P\n7:30-3:30", "P\n7:35-3:25", "P\n7:30-3:30", "P\n7:30-3:40", "P\n7:30-3:30", "Part-Time", "✓"),

        # MISMATCH: Marked present but auth expired (should be OD)
        ("Johnson, Noah", "987654324", "P\n7:45-4:00", "P\n7:50-3:55", "OD\n---", "OD\n---", "OD\n---", "Full-Time", "✓"),

        # MISMATCH: Times don't match Brightwheel (30 min difference)
        ("Williams, Ava", "987654325", "P\n9:00-5:30", "P\n9:05-5:25", "P\n9:00-5:30", "P\n8:55-5:35", "P\n9:00-5:30", "Full-Time", "✓"),

        # MISMATCH: Absent with no note
        ("Martinez, Sophia", "987654326", "AB\n---", "AB\n---", "P\n7:15-4:30", "P\n7:20-4:25", "P\n7:15-4:30", "Full-Time", ""),

        # MISMATCH: APT changed mid-week (was Full-Time, now Part-Time)
        ("Lee, Jackson", "987654327", "P\n7:00-5:00", "P\n7:05-4:55", "P\n7:00-3:00", "P\n7:00-3:00", "P\n7:00-3:00", "Part-Time*", "✓"),

        ("Brown, Lucas", "987654328", "P\n7:30-4:30", "P\n7:35-4:25", "P\n7:30-4:30", "P\n7:30-4:35", "P\n7:30-4:30", "Full-Time", "✓"),
        ("Kim, Isabella", "987654329", "P\n8:15-3:15", "P\n8:20-3:10", "P\n8:15-3:15", "P\n8:15-3:20", "P\n8:15-3:15", "Part-Time", "✓"),
        ("Anderson, Mia", "987654330", "P\n7:00-4:00", "P\n7:05-3:55", "P\n7:00-4:00", "P\n7:00-4:05", "P\n7:00-4:00", "Full-Time", "✓"),
    ]

    for student in students:
        data.append(list(student))

    # Create table
    table = Table(data, colWidths=[1.2*inch, 1.0*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.7*inch])
    table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),

        # Data rows
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 1), (1, -1), 'LEFT'),
        ('ALIGN', (2, 1), (-2, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),

        # Alternating rows
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.beige]),
    ]))

    story.append(table)
    story.append(Spacer(1, 0.2*inch))

    # Footer notes
    note_style = ParagraphStyle('Note', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
    story.append(Paragraph("<b>Status Codes:</b> P (Present), AB (Absent), OD (Off Day - not authorized)", note_style))
    story.append(Paragraph("<b>*APT Type changed:</b> Jackson Lee authorization changed from Full-Time to Part-Time on 5/7.", note_style))
    story.append(Paragraph("<b>WARNING: Missing Signature:</b> Sophia Martinez absences require parent note.", note_style))

    doc.build(story)
    print(f"[OK] Created {output_path}")
    print("  Test cases:")
    print("    - 3 perfect matches")
    print("    - 1 expired authorization (Noah Johnson - OD on Wed-Fri)")
    print("    - 1 time mismatch (Ava Williams - 30min difference)")
    print("    - 1 missing absence note (Sophia Martinez)")
    print("    - 1 APT type change (Jackson Lee - FT->PT mid-week)")


# ============================================================================
# 2. CACFP MEAL COUNT REPORT
# ============================================================================

def generate_cacfp_report():
    """
    Creates a CACFP Weekly Meal Count with Attendance by FRP.

    Format from: https://www.myfoodprogram.com/

    Includes:
    - FRP categories (Free, Reduced, Paid)
    - Meal codes: B (Breakfast), AM (AM Snack), L (Lunch), P (PM Snack), S (Supper), E (Evening)
    - Non-payable meal violations (double snacks, missing components)
    """
    output_path = Path("data/cacfp_meal_count.pdf")
    output_path.parent.mkdir(exist_ok=True)

    doc = SimpleDocTemplate(str(output_path), pagesize=landscape(letter),
                           topMargin=0.5*inch, bottomMargin=0.5*inch)

    story = []
    styles = getSampleStyleSheet()

    # Header
    header_style = ParagraphStyle('Header', parent=styles['Heading1'], fontSize=14,
                                  textColor=colors.HexColor('#2E7D32'), alignment=TA_CENTER, spaceAfter=6)
    story.append(Paragraph("CACFP Weekly Meal Count with Attendance by FRP", header_style))
    story.append(Paragraph("Week of May 5-9, 2026", ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, spaceAfter=12)))
    story.append(Spacer(1, 0.2*inch))

    # Provider info
    info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=9)
    story.append(Paragraph("<b>Provider:</b> Little Stars Academy | <b>License #:</b> 123456 | <b>Sponsoring Org:</b> My Food Program", info_style))
    story.append(Spacer(1, 0.2*inch))

    # Meal count table
    data = [
        ['Child Name', 'FRP', 'Monday 5/5', 'Tuesday 5/6', 'Wednesday 5/7', 'Thursday 5/8', 'Friday 5/9', 'Total']
    ]

    # Students with meal records
    students = [
        # Free eligibility
        ("Rodriguez, Emma", "Free", "B/AM/L/P", "B/AM/L/P", "B/AM/L/P", "B/AM/L/P", "B/AM/L/P", "20"),
        ("Chen, Liam", "Free", "B/AM/L/P", "B/AM/L/P", "B/AM/L/P", "B/AM/L/P", "B/AM/L/P", "20"),
        ("Martinez, Sophia", "Free", "---", "---", "B/AM/L/P", "B/AM/L/P", "B/AM/L/P", "12"),
        ("Anderson, Mia", "Free", "B/L/P/S", "B/L/P/S", "B/L/P/S", "B/L/P/S", "B/L/P/S", "20"),

        # Reduced eligibility
        ("Patel, Olivia", "Reduced", "B/AM/L", "B/AM/L", "B/AM/L", "B/AM/L", "B/AM/L", "15"),
        ("Lee, Jackson", "Reduced", "B/AM/L", "B/AM/L", "AM/L", "AM/L", "AM/L", "11"),
        ("Kim, Isabella", "Reduced", "B/AM/L/P", "B/AM/L/P", "B/AM/L/P", "B/AM/L/P", "B/AM/L/P", "20"),

        # Paid eligibility
        ("Johnson, Noah", "Paid", "B/AM/L/P", "B/AM/L/P", "---", "---", "---", "8"),
        ("Williams, Ava", "Paid", "B/L/P/S", "B/L/P/S", "B/L/P/S", "B/L/P/S", "B/L/P/S", "20"),
        ("Brown, Lucas", "Paid", "B/AM/L/P", "B/AM/L/P", "B/AM/L/P", "B/AM/L/P", "B/AM/L/P", "20"),

        # NON-PAYABLE VIOLATION: Double snack (AM + P in same period)
        ("Garcia, Ethan", "Free", "B/AM/L/P", "B/AM/P/P", "B/AM/L/P", "B/AM/L/P", "B/AM/L/P", "21*"),

        # NON-PAYABLE: Claimed supper without evening care authorization
        ("Davis, Charlotte", "Reduced", "B/AM/L/P/S", "B/AM/L/P/S", "B/AM/L/P", "B/AM/L/P", "B/AM/L/P", "19*"),
    ]

    for student in students:
        data.append(list(student))

    # Summary row
    data.append(['', '', '', '', '', '', 'Total Meals:', '206'])

    # Create table
    table = Table(data, colWidths=[1.3*inch, 0.8*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.1*inch, 0.7*inch])
    table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),

        # Data
        ('FONTSIZE', (0, 1), (-1, -2), 7),
        ('ALIGN', (2, 1), (-1, -1), 'CENTER'),

        # Summary row
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.beige]),
    ]))

    story.append(table)
    story.append(Spacer(1, 0.2*inch))

    # Footer notes
    note_style = ParagraphStyle('Note', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
    story.append(Paragraph("<b>Meal Codes:</b> B=Breakfast, AM=AM Snack, L=Lunch, P=PM Snack, S=Supper, E=Evening Snack", note_style))
    story.append(Paragraph("<b>FRP:</b> Free/Reduced/Paid eligibility based on family income", note_style))
    story.append(Paragraph("<b>WARNING: Non-Payable Meals (marked *):</b>", note_style))
    story.append(Paragraph("  • Ethan Garcia (Tue): Double PM snack claimed (P/P) - only 1 snack per period allowed", note_style))
    story.append(Paragraph("  • Charlotte Davis (Mon-Tue): Supper claimed without evening care authorization", note_style))

    doc.build(story)
    print(f"[OK] Created {output_path}")
    print("  Test cases:")
    print("    - 9 valid meal claims")
    print("    - 1 double snack violation (Ethan Garcia)")
    print("    - 1 unauthorized supper claim (Charlotte Davis)")


# ============================================================================
# 3. MESSY ROSTER UPLOAD
# ============================================================================

def generate_messy_roster():
    """
    Creates a "messy" CSV that tests data normalization.

    Schema from: https://help.mybrightwheel.com/en/articles/11548710

    Issues to fix:
    - Merged parent fields ("Jane D. / Parent: Mark / 555-0199")
    - Wrong date formats
    - Invalid status values
    - Missing required fields
    - Phone numbers without country code
    - Multiple allergies in wrong format
    """
    output_path = Path("data/messy_roster.csv")
    output_path.parent.mkdir(exist_ok=True)

    # Messy data (intentionally broken)
    messy_data = [
        # Headers (some missing, some misspelled)
        ["Student First", "Student Last", "DOB", "Status", "HomeRoom", "Parent Info", "Phone", "Allergies", "Income"],

        # Row 1: Merged parent fields
        ["Emma", "Rodriguez", "3/15/2022", "Active", "Toddlers", "Maria Rodriguez / maria.r@email.com", "555-0123", "peanuts", "$30,000-$40,000"],

        # Row 2: Wrong date format
        ["Liam", "Chen", "2022-11-08", "active", "Toddlers", "Wei Chen", "5550124", "none", "Free"],

        # Row 3: Invalid status
        ["Olivia", "Patel", "6/22/2021", "enrolled", "Preschool", "Priya Patel / priya@email.com", "(555) 012-5678", "Dairy; Eggs", "Reduced"],

        # Row 4: Missing required email
        ["Noah", "Johnson", "4/10/2022", "Active", "Toddlers", "Sarah Johnson", "555-0126", "", "$50,000-$75,000"],

        # Row 5: Multiple contacts merged
        ["Ava", "Williams", "1/30/2023", "Active", "Infants", "Mom: Lisa 555-0127 / Dad: Mike 555-0128", "", "none", "Paid"],

        # Row 6: Handwritten format (spaces, capitalization)
        ["sophia", "MARTINEZ", "09/15/2021", "ACTIVE", "preschool", "Ana Martinez / ana.martinez@email.com", "555 0129", "shellfish, tree nuts", "$25,000"],

        # Row 7: Good data (baseline)
        ["Jackson", "Lee", "7/18/2022", "Active", "Toddlers", "Min Lee / min.lee@email.com", "555-0130", "", "$100,000+"],

        # Row 8: Wrong room name (doesn't exist)
        ["Isabella", "Kim", "12/3/2021", "Active", "Kindergarten", "Sun Kim / sun.kim@email.com", "555-0131", "none", "Free"],

        # Row 9: Missing homeroom
        ["Lucas", "Brown", "5/22/2023", "Active", "", "Emily Brown / emily.b@email.com", "555-0132", "", "Reduced"],

        # Row 10: International phone number
        ["Mia", "Anderson", "2/14/2022", "Active", "Toddlers", "Anna Anderson / anna@email.com", "+44 20 7123 4567", "gluten", "$40,000-$50,000"],
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(messy_data)

    print(f"[OK] Created {output_path}")
    print("  Data quality issues:")
    print("    - Wrong column headers")
    print("    - Merged parent fields (3 students)")
    print("    - Invalid date formats (2 students)")
    print("    - Invalid status values (1 student)")
    print("    - Missing required fields (2 students)")
    print("    - Phone format variations (4 types)")
    print("    - Allergy format issues (semicolon vs comma)")


# ============================================================================
# 4. BRIGHTWHEEL DATABASE MOCK
# ============================================================================

def generate_brightwheel_database():
    """
    Creates a mock Brightwheel database for comparison.

    This is what the agent will query to reconcile against the reports.
    """
    output_path = Path("data/brightwheel_database.json")
    output_path.parent.mkdir(exist_ok=True)

    database = {
        "students": [
            {
                "brightwheel_id": "BW-1001",
                "first_name": "Emma",
                "last_name": "Rodriguez",
                "birthdate": "2022-03-15",
                "kinderconnect_id": "987654321",
                "status": "Active",
                "homeroom": "Toddlers",
                "frp_category": "Free",
                "allergies": ["peanuts"],
                "subsidy": True,
                "apt_type": "Full-Time",
                "check_ins": [
                    {"date": "2026-05-05", "in": "07:15", "out": "16:30"},
                    {"date": "2026-05-06", "in": "07:20", "out": "16:15"},
                    {"date": "2026-05-07", "in": "07:10", "out": "16:45"},
                    {"date": "2026-05-08", "in": "07:25", "out": "16:20"},
                    {"date": "2026-05-09", "in": "07:15", "out": "16:30"},
                ],
                "meals_served": {
                    "2026-05-05": ["B", "AM", "L", "P"],
                    "2026-05-06": ["B", "AM", "L", "P"],
                    "2026-05-07": ["B", "AM", "L", "P"],
                    "2026-05-08": ["B", "AM", "L", "P"],
                    "2026-05-09": ["B", "AM", "L", "P"],
                },
                "parent_1_name": "Maria Rodriguez",
                "parent_1_email": "maria.r@email.com",
                "parent_1_phone": "555-0123",
            },
            {
                "brightwheel_id": "BW-1002",
                "first_name": "Liam",
                "last_name": "Chen",
                "birthdate": "2021-11-08",
                "kinderconnect_id": "987654322",
                "status": "Active",
                "homeroom": "Toddlers",
                "frp_category": "Free",
                "allergies": [],
                "subsidy": True,
                "apt_type": "Full-Time",
                "check_ins": [
                    {"date": "2026-05-05", "in": "08:00", "out": "17:00"},
                    {"date": "2026-05-06", "in": "08:05", "out": "17:05"},
                    {"date": "2026-05-07", "in": "08:00", "out": "17:00"},
                    {"date": "2026-05-08", "in": "07:55", "out": "17:10"},
                    {"date": "2026-05-09", "in": "08:00", "out": "17:00"},
                ],
                "meals_served": {
                    "2026-05-05": ["B", "AM", "L", "P"],
                    "2026-05-06": ["B", "AM", "L", "P"],
                    "2026-05-07": ["B", "AM", "L", "P"],
                    "2026-05-08": ["B", "AM", "L", "P"],
                    "2026-05-09": ["B", "AM", "L", "P"],
                },
                "parent_1_name": "Wei Chen",
                "parent_1_email": "wei.chen@email.com",
                "parent_1_phone": "555-0124",
            },
            # ... (Add remaining students)
            {
                "brightwheel_id": "BW-1004",
                "first_name": "Noah",
                "last_name": "Johnson",
                "birthdate": "2022-04-10",
                "kinderconnect_id": "987654324",
                "status": "Active",
                "homeroom": "Toddlers",
                "frp_category": "Paid",
                "allergies": [],
                "subsidy": True,
                "apt_type": "Full-Time",
                "authorization_end": "2026-05-06",  # EXPIRED on Wed
                "check_ins": [
                    {"date": "2026-05-05", "in": "07:45", "out": "16:00"},
                    {"date": "2026-05-06", "in": "07:50", "out": "15:55"},
                    # No check-ins Wed-Fri (expired auth)
                ],
                "meals_served": {
                    "2026-05-05": ["B", "AM", "L", "P"],
                    "2026-05-06": ["B", "AM", "L", "P"],
                },
                "parent_1_name": "Sarah Johnson",
                "parent_1_email": "sarah.j@email.com",
                "parent_1_phone": "555-0126",
            },
            {
                "brightwheel_id": "BW-1005",
                "first_name": "Ava",
                "last_name": "Williams",
                "birthdate": "2023-01-30",
                "kinderconnect_id": "987654325",
                "status": "Active",
                "homeroom": "Infants",
                "frp_category": "Paid",
                "allergies": [],
                "subsidy": True,
                "apt_type": "Full-Time",
                "check_ins": [
                    # MISMATCH: Brightwheel shows 8:30 check-in, KinderConnect shows 9:00
                    {"date": "2026-05-05", "in": "08:30", "out": "17:30"},
                    {"date": "2026-05-06", "in": "08:35", "out": "17:25"},
                    {"date": "2026-05-07", "in": "08:30", "out": "17:30"},
                    {"date": "2026-05-08", "in": "08:25", "out": "17:35"},
                    {"date": "2026-05-09", "in": "08:30", "out": "17:30"},
                ],
                "meals_served": {
                    "2026-05-05": ["B", "L", "P", "S"],
                    "2026-05-06": ["B", "L", "P", "S"],
                    "2026-05-07": ["B", "L", "P", "S"],
                    "2026-05-08": ["B", "L", "P", "S"],
                    "2026-05-09": ["B", "L", "P", "S"],
                },
                "parent_1_name": "Lisa Williams",
                "parent_1_email": "lisa.w@email.com",
                "parent_1_phone": "555-0127",
            },
        ],
        "rooms": ["Infants", "Toddlers", "Preschool"],
        "generated_at": date.today().isoformat()
    }

    with open(output_path, 'w') as f:
        json.dump(database, f, indent=2)

    print(f"[OK] Created {output_path}")
    print("  Database includes:")
    print("    - 5 students with full records")
    print("    - Check-in times for reconciliation")
    print("    - Meal service records")
    print("    - Authorization expiration dates")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Generate all sample data files."""
    print("=" * 70)
    print("GENERATING BRIGHTWHEEL SAMPLE DATA")
    print("=" * 70)
    print()

    Path("data").mkdir(exist_ok=True)

    print("[1/4] KinderConnect Attendance Report")
    generate_kinderconnect_report()
    print()

    print("[2/4] CACFP Meal Count Report")
    generate_cacfp_report()
    print()

    print("[3/4] Messy Roster Upload")
    generate_messy_roster()
    print()

    print("[4/4] Brightwheel Database (Mock)")
    generate_brightwheel_database()
    print()

    print("=" * 70)
    print("[SUCCESS] SAMPLE DATA GENERATION COMPLETE")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Review generated files in data/ directory")
    print("  2. Run: python reconcile.py data/kinderconnect_report.pdf")
    print("  3. See EXPLANATION.md for how it works")


if __name__ == "__main__":
    main()
