"""Generate five demo eval-cases — annual-visit patients across the lifespan,
with summaries of deliberately varying fidelity to their source notes.

Run from anywhere:  python examples/generate_demo_cases.py
Creates the cases + pasted (manual) notes locally under data/ via the service
layer (no FHIR / no API keys needed). Re-running overwrites them.
"""

import os
import sys

# Make the repo root importable + the working dir, so data/ lands there.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import service  # noqa: E402


CASES = [
    # ---------------------------------------------------------------- 12yo
    {
        "id": "demo-maya-12",
        "summary": (
            "12-year-old healthy female here for a well-child visit. Growth and "
            "development are on track with BMI at the 50th percentile. Immunizations "
            "are up to date; she received Tdap and the first HPV vaccine today. "
            "Vision and hearing screening were normal. She has no chronic medical "
            "problems and takes no daily medications. Mild seasonal allergic rhinitis "
            "is managed with PRN cetirizine. Depression screening was negative. "
            "Anticipatory guidance was provided on nutrition, physical activity, and "
            "screen time. She is doing well in 7th grade."
        ),
        "notes": [
            ("Well-Child Visit", "2026-06-02", "Well-child visit, 12yo female. Doing well, active in soccer, normal appetite and sleep. No complaints. 7th grade, good grades. Exam unremarkable. Plan: routine well-child care, return in 1 year."),
            ("Vitals", "2026-06-02", "Height 152 cm (55th %ile), Weight 43 kg (50th %ile), BMI 18.6 (50th %ile). BP 102/64, HR 78, Temp 36.8C."),
            ("Immunization", "2026-06-02", "Administered today: Tdap; HPV #1 of 2-dose series. Influenza 2025-10. Up to date on childhood series."),
            ("Screening", "2026-06-02", "Vision 20/20 OD and OS. Audiometry passed bilaterally."),
            ("Problem List", "2026-06-02", "Allergic rhinitis, seasonal."),
            ("Medication List", "2026-06-02", "Cetirizine 10 mg PO once daily PRN seasonal allergy symptoms. No daily medications."),
            ("Screening", "2026-06-02", "Adolescent depression screen (PHQ-A): score 1, negative."),
            ("Nursing Note", "2026-06-02", "Anticipatory guidance: balanced nutrition, 60 minutes daily activity, limit recreational screen time, helmet and seatbelt safety. Mother present, no concerns."),
            ("Well-Child Visit", "2025-05-20", "12-month interval well-child. Normal growth (BMI 45th %ile), development appropriate. No issues."),
            ("Telephone Encounter", "2026-03-10", "Mother called regarding a small dry skin patch on the elbow. Advised OTC emollient. Per portal follow-up, resolved."),
            ("Social History", "2026-06-02", "Lives with both parents and a younger sibling. Doing well academically. No safety concerns."),
        ],
    },
    # ---------------------------------------------------------------- 25yo
    {
        "id": "demo-jordan-25",
        "summary": (
            "25-year-old healthy male presenting for an annual examination. He has no "
            "chronic medical conditions. He reports occasional tension headaches "
            "relieved by over-the-counter ibuprofen. Social history is notable for "
            "moderate alcohol use of about six drinks per week and daily nicotine "
            "vaping, for which he was counseled on cessation. CBC and metabolic panel "
            "are within normal limits; a preliminary mildly elevated ALT on initial "
            "labs normalized on repeat testing. BMI is 27, in the overweight range, "
            "and diet and exercise were discussed. Immunizations are up to date and "
            "his depression screen was negative."
        ),
        "notes": [
            ("Annual Exam", "2026-06-01", "25yo male for annual exam. Feels well. Software engineer, sedentary job. Occasional tension-type headaches relieved with ibuprofen. No chronic conditions. Exam normal."),
            ("Vitals", "2026-06-01", "Height 178 cm, Weight 86 kg, BMI 27.1. BP 124/78, HR 70."),
            ("Lab Result", "2026-05-18", "Initial labs. CBC normal. CMP: ALT 68 U/L (HIGH, ref <40), AST 35, alk phos and bilirubin normal, glucose 92, creatinine 0.9. Mild transaminitis; recommend repeat — consider hepatic steatosis vs alcohol."),
            ("Lab Result", "2026-06-01", "Repeat hepatic panel: ALT 32 U/L (normal), AST 28 U/L (normal). Resolved."),
            ("Lab Result", "2026-06-01", "Lipid panel: total cholesterol 195, LDL 120, HDL 45, triglycerides 150."),
            ("Social History", "2026-06-01", "Alcohol approximately 6 drinks/week. Vapes nicotine daily. Denies other substances."),
            ("Medication List", "2026-06-01", "Ibuprofen 400 mg PO PRN headache. No chronic medications."),
            ("Immunization", "2026-06-01", "Tdap 2023. COVID-19 vaccine current. Influenza 2025-11."),
            ("Screening", "2026-06-01", "PHQ-9 score 3, negative for depression."),
            ("Counseling Note", "2026-06-01", "Counseled on alcohol moderation and nicotine vaping cessation; provided cessation resources."),
            ("Annual Exam", "2025-05-30", "Prior annual exam. Healthy, BMI 26, labs normal."),
        ],
    },
    # ---------------------------------------------------------------- 40yo
    {
        "id": "demo-dana-40",
        "summary": (
            "40-year-old female with hypertension and prediabetes here for her annual "
            "exam. Her blood pressure is well controlled on lisinopril 20 mg daily. "
            "Her most recent hemoglobin A1c is 6.0%, improved with lifestyle changes. "
            "BMI is 33. She is on sertraline 50 mg for depression with a good "
            "response, and her PHQ-9 today was 4. She exercises three times per week. "
            "Mammogram is up to date and normal. The plan is continued lifestyle "
            "modification with a repeat A1c in six months."
        ),
        "notes": [
            ("Annual Exam", "2026-06-03", "40yo female with HTN, prediabetes, obesity, and depression for annual exam. Reports feeling stable but stressed at work. Adherent to medications."),
            ("Vitals", "2026-06-03", "BP 148/92, repeat 150/94. Height 165 cm, Weight 90 kg, BMI 33.1, HR 82."),
            ("Medication List", "2026-06-03", "Lisinopril 20 mg daily; metformin 500 mg twice daily; sertraline 50 mg daily."),
            ("Lab Result", "2026-06-03", "Hemoglobin A1c 6.3%."),
            ("Lab Result", "2025-12-10", "Hemoglobin A1c 6.1%."),
            ("Lab Result", "2026-06-03", "Lipid panel: LDL 140, HDL 42, triglycerides 180."),
            ("Screening", "2026-06-03", "PHQ-9 score 9 (mild-to-moderate). Depression partially controlled; consider increasing sertraline dose or referral to therapy."),
            ("Problem List", "2026-06-03", "Essential hypertension; prediabetes; obesity; major depressive disorder."),
            ("Imaging", "2025-10-05", "Screening mammogram BI-RADS 2, benign findings."),
            ("Nursing Note", "2026-06-03", "Patient reports exercising about once per week and would like to increase activity. Diet high in processed foods."),
            ("Annual Exam", "2025-06-12", "Prior visit: BP 145/90; A1c 6.0%. Counseled on lifestyle; blood pressure not at goal."),
        ],
    },
    # ---------------------------------------------------------------- 65yo
    {
        "id": "demo-robert-65",
        "summary": (
            "65-year-old male with coronary artery disease status post coronary stent, "
            "type 2 diabetes mellitus, and hyperlipidemia, here for his annual visit. "
            "His medications include atorvastatin 80 mg, aspirin 81 mg, metoprolol, "
            "and metformin. His LDL is at goal at 65 mg/dL and his A1c is 7.2%, "
            "improved from prior. He was recently started on empagliflozin for "
            "glycemic control and its cardiovascular benefit. Renal function is "
            "stable, consistent with CKD stage 3 (eGFR 48). He reports good exercise "
            "tolerance and walks two miles without chest pain. Colonoscopy is up to "
            "date. He was also started on amoxicillin for his blood pressure."
        ),
        "notes": [
            ("Annual Exam", "2026-06-02", "65yo male. CAD s/p PCI with drug-eluting stent 2022. T2DM, hyperlipidemia, CKD stage 3, BPH. No angina; walks 2 miles daily with good exercise tolerance."),
            ("Vitals", "2026-06-02", "BP 132/78, HR 64, BMI 29."),
            ("Medication List", "2026-06-02", "Atorvastatin 80 mg; aspirin 81 mg; metoprolol succinate 50 mg; metformin 1000 mg twice daily; empagliflozin 10 mg (started 2026-04); tamsulosin 0.4 mg."),
            ("Lab Result", "2026-06-02", "Lipid panel: LDL 65, HDL 40, triglycerides 130. LDL at goal for secondary prevention."),
            ("Lab Result", "2026-06-02", "Hemoglobin A1c 7.2% (prior 7.6%)."),
            ("Lab Result", "2026-06-02", "Creatinine 1.5, eGFR 48 mL/min (stable; prior eGFR 50). CKD stage 3."),
            ("Specialist Consult", "2026-03-15", "Cardiology: stable CAD on guideline-directed medical therapy. Exercise stress test negative for ischemia. Continue current regimen."),
            ("Imaging", "2024-08-01", "Screening colonoscopy normal; repeat in 8-10 years."),
            ("Lab Result", "2025-06-01", "Prior labs: A1c 7.6%, LDL 80."),
            ("Telephone Encounter", "2026-04-20", "Empagliflozin started for glycemic control and cardiovascular/renal benefit; tolerating well, no genitourinary symptoms."),
            ("Problem List", "2026-06-02", "CAD s/p stent; type 2 diabetes mellitus; hyperlipidemia; CKD stage 3; benign prostatic hyperplasia."),
        ],
    },
    # ---------------------------------------------------------------- 80yo
    {
        "id": "demo-eleanor-80",
        "summary": (
            "80-year-old woman with atrial fibrillation, heart failure with preserved "
            "ejection fraction, osteoporosis, and hypothyroidism, presenting for "
            "annual care. She is anticoagulated with apixaban for stroke prevention, "
            "and her thyroid function is normal on levothyroxine 88 mcg. She has had "
            "no falls in the past year. A recent chest X-ray raised concern for a lung "
            "nodule, but a dedicated CT confirmed a benign calcified granuloma "
            "requiring no follow-up. She remains independent in her activities of "
            "daily living. Bone density confirms osteoporosis, for which she takes "
            "alendronate. She was advised to take ibuprofen daily for joint pain."
        ),
        "notes": [
            ("Annual Exam", "2026-06-04", "80yo female with atrial fibrillation, HFpEF, osteoporosis, hypothyroidism, and mild cognitive impairment. Lives alone, daughter nearby and involved. Here for annual care."),
            ("Vitals", "2026-06-04", "BP 138/76, HR 72 irregularly irregular. Weight stable."),
            ("Medication List", "2026-06-04", "Apixaban 5 mg twice daily; metoprolol 25 mg; furosemide 20 mg; levothyroxine 88 mcg; alendronate 70 mg weekly; calcium/vitamin D; donepezil 5 mg."),
            ("Lab Result", "2026-06-04", "TSH 2.1 (normal)."),
            ("Imaging", "2026-04-22", "Chest X-ray: possible 8 mm nodule, right upper lobe. Recommend dedicated CT for characterization."),
            ("Imaging", "2026-05-05", "Chest CT: 8 mm calcified granuloma, right upper lobe. Benign. No follow-up imaging required."),
            ("PT Note", "2026-02-10", "Evaluation after a fall at home; no injury. Gait instability noted; home exercises and review of fall precautions."),
            ("Nursing Note", "2026-06-04", "Patient reports two falls in the past year, no fractures. Uses a cane intermittently."),
            ("DEXA", "2025-07-01", "Femoral neck T-score -2.8: osteoporosis."),
            ("Cognitive Assessment", "2026-01-15", "MoCA 22/30, consistent with mild cognitive impairment. On donepezil."),
            ("Specialist Consult", "2025-11-20", "Cardiology: atrial fibrillation, rate-controlled. CHA2DS2-VASc elevated; continue apixaban. HFpEF stable on diuretic."),
            ("Caregiver Note", "2026-06-04", "Daughter reports the patient needs help managing medications and finances; independent in basic ADLs (bathing, dressing) but not all instrumental ADLs."),
        ],
    },
]


def main():
    for c in CASES:
        case = service.create_case(
            summary_text=c["summary"],
            case_id=c["id"],
            pasted_notes=[{"text": text, "type": ntype, "date": date} for ntype, date, text in c["notes"]],
            summary_source="demo",
        )
        print(f"✓ {case['case_id']:<20} {len(case['source_note_ids'])} notes")
    print(f"\nCreated {len(CASES)} demo cases. Open them in the Summary Explorer and Run jury.")


if __name__ == "__main__":
    main()
