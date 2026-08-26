from __future__ import annotations

import random
from dataclasses import replace

from app.models import Company, Dataset, EventLog, Interview, Panel, Room, Student
from app.time_utils import at, day_end, day_start

BRANCHES = ["CSE", "IT", "ECE", "EEE", "Mechanical", "Civil", "Chemical", "AI/DS"]
BRANCH_WEIGHTS = [0.23, 0.17, 0.15, 0.10, 0.12, 0.09, 0.06, 0.08]
FIRST_NAMES = [
    "Aarav", "Aditi", "Arjun", "Diya", "Ishan", "Kavya", "Meera", "Nikhil",
    "Pranav", "Riya", "Saanvi", "Vihaan", "Ananya", "Dev", "Ira", "Kabir",
    "Maya", "Neel", "Tara", "Yash", "Aditya", "Fatima", "Gauri", "Harsh",
    "Jai", "Krisha", "Lavanya", "Manav", "Noor", "Om", "Pooja", "Rehan",
]
LAST_NAMES = [
    "Sharma", "Iyer", "Patel", "Rao", "Menon", "Gupta", "Nair", "Das",
    "Bose", "Kulkarni", "Mehta", "Khan", "Reddy", "Singh", "Chatterjee",
    "Pillai", "Joshi", "Kapoor", "Verma", "Saxena", "Shetty", "Banerjee",
]


def _company_specs() -> list[dict]:
    tech = ["CSE", "IT", "AI/DS", "ECE"]
    broad = BRANCHES
    core_mech = ["Mechanical", "EEE", "ECE", "Civil", "Chemical"]
    core_elec = ["ECE", "EEE", "CSE", "IT", "AI/DS"]
    return [
        ("NovaPay", 1, "fintech", 1, 8.7, tech, 58, 45, 4, 9),
        ("Quantix Systems", 1, "premium/product", 1, 8.8, tech, 52, 60, 3, 9),
        ("Aether Semiconductor", 1, "semiconductor", 1, 8.4, core_elec, 80, 45, 4, 9),
        ("BluePeak Consulting", 1, "consulting", 1, 8.2, broad, 120, 30, 5, 10),
        ("Orbit Technologies", 1, "premium/product", 1, 8.5, tech, 75, 45, 4, 9),
        ("Zenith Digital", 1, "SaaS", 1, 8.0, tech, 110, 30, 5, 9),
        ("Nimbus Cloud", 1, "SaaS", 1, 8.2, tech, 95, 30, 5, 10),
        ("VectorWorks", 1, "premium/product", 1, 8.9, tech, 42, 60, 2, 9),
        ("Terra Motors", 2, "core engineering", 2, 7.4, core_mech, 130, 30, 5, 9),
        ("HelioGrid Energy", 2, "core engineering", 2, 7.2, core_mech, 125, 30, 4, 10),
        ("Cobalt Analytics", 2, "consulting", 2, 7.8, broad, 145, 30, 5, 9),
        ("PulseStack", 2, "startup", 2, 7.5, tech, 95, 30, 3, 11),
        ("FinEdge Labs", 2, "fintech", 2, 7.9, tech, 105, 30, 4, 9),
        ("MechaForge", 2, "core engineering", 2, 7.0, core_mech, 140, 20, 5, 9),
        ("Datavine", 2, "SaaS", 2, 7.4, tech, 150, 20, 5, 10),
        ("Stratos Mobility", 2, "core engineering", 2, 7.2, ["Mechanical", "EEE", "ECE", "CSE"], 110, 30, 4, 10),
        ("Vertex Micro", 2, "semiconductor", 2, 7.6, core_elec, 115, 30, 4, 9),
        ("ClearPath AI", 2, "startup", 2, 8.0, tech, 70, 45, 3, 12),
        ("Bridgewater Digital", 2, "consulting", 2, 7.1, broad, 180, 20, 6, 9),
        ("Redwood Systems", 3, "mass recruiter", 3, 6.5, broad, 310, 15, 9, 9),
        ("Silverline Tech", 3, "mass recruiter", 3, 6.4, broad, 285, 15, 8, 9),
        ("Northstar Services", 3, "mass recruiter", 3, 6.2, broad, 260, 20, 7, 10),
        ("Praxis Global", 3, "consulting", 3, 6.8, broad, 210, 20, 6, 9),
        ("Indigo Cloudworks", 3, "SaaS", 3, 6.9, tech + ["EEE"], 190, 20, 5, 11),
        ("Axion Materials", 3, "core engineering", 3, 6.7, core_mech, 170, 20, 5, 10),
        ("Lattice Infra", 3, "core engineering", 3, 6.3, ["Civil", "Mechanical", "EEE"], 155, 20, 4, 9),
        ("KiteFin", 2, "fintech", 3, 7.3, tech, 135, 30, 4, 12),
        ("BrightMesa", 3, "startup", 3, 6.6, broad, 165, 20, 4, 13),
        ("SynapseWorks", 2, "premium/product", 4, 7.8, tech, 115, 30, 4, 9),
        ("Cedar Robotics", 2, "core engineering", 4, 7.2, ["Mechanical", "ECE", "EEE", "CSE", "AI/DS"], 105, 30, 3, 10),
        ("Riverbend Labs", 3, "startup", 4, 6.8, tech, 125, 20, 3, 11),
        ("Atlas Manufacturing", 3, "core engineering", 4, 6.4, core_mech, 180, 20, 5, 9),
        ("CloudHarbor", 3, "SaaS", 4, 6.7, tech + ["ECE"], 170, 20, 5, 10),
        ("Meridian Ops", 3, "mass recruiter", 4, 6.0, broad, 330, 15, 10, 9),
        ("Sparkline Digital", 3, "SaaS", 4, 6.5, broad, 240, 15, 7, 12),
    ]


def _student_name(rng: random.Random, idx: int) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def _cgpa(rng: random.Random, branch: str) -> float:
    branch_boost = {"CSE": 0.12, "IT": 0.06, "AI/DS": 0.10, "ECE": 0.02}.get(branch, -0.03)
    value = rng.gauss(7.45 + branch_boost, 0.82)
    if rng.random() < 0.09:
        value += rng.uniform(0.55, 1.15)
    if rng.random() < 0.08:
        value -= rng.uniform(0.45, 1.0)
    return round(max(5.5, min(10.0, value)), 2)


def _make_companies() -> tuple[list[Company], list[Panel]]:
    companies: list[Company] = []
    panels: list[Panel] = []
    for idx, spec in enumerate(_company_specs(), start=1):
        name, tier, ctype, day, cutoff, branches, shortlist, duration, panel_count, start_hour = spec
        cid = f"C{idx:02d}"
        start = at(day, start_hour)
        end_hour = 17 if ctype in {"premium/product", "startup"} else 18
        end = at(day, end_hour, 30 if end_hour == 17 else 0)
        company = Company(
            id=cid,
            name=name,
            priority_tier=tier,
            company_type=ctype,
            day_preference=day,
            cgpa_cutoff=cutoff,
            eligible_branches=list(dict.fromkeys(branches)),
            shortlist_size=shortlist,
            interview_duration=duration,
            panel_count=panel_count,
            preferred_start=start,
            available_start=start,
            available_end=end,
            expected_arrival=start,
        )
        companies.append(company)
        for panel_idx in range(1, panel_count + 1):
            panels.append(
                Panel(
                    id=f"P{idx:02d}-{panel_idx:02d}",
                    company_id=cid,
                    name=f"{name} Panel {panel_idx}",
                    active=True,
                    available_from=start,
                    available_until=end,
                )
            )
    return companies, panels


def _make_rooms() -> list[Room]:
    rooms: list[Room] = []
    for idx in range(1, 21):
        day = 1
        rooms.append(
            Room(
                id=f"R{idx:02d}",
                name=f"Interview Room {idx:02d}",
                building="Placement Block" if idx <= 12 else "Innovation Center",
                floor=1 + ((idx - 1) // 5),
                available=True,
                available_from=day_start(day),
                available_until=day_end(4),
                room_type="large" if idx in {1, 2, 3, 4} else "standard",
            )
        )
    return rooms


def generate_dataset(seed: int = 42) -> Dataset:
    rng = random.Random(seed)
    companies, panels = _make_companies()
    students: list[Student] = []
    for idx in range(1, 801):
        branch = rng.choices(BRANCHES, weights=BRANCH_WEIGHTS, k=1)[0]
        cgpa = _cgpa(rng, branch)
        students.append(
            Student(
                id=f"S{idx:04d}",
                name=_student_name(rng, idx),
                roll_number=f"23{branch.replace('/', '')}{idx:04d}",
                branch=branch,
                cgpa=cgpa,
                placement_status="eligible",
                shortlisted_company_ids=[],
                available_from=day_start(1),
                available_until=day_end(4),
                priority_score=round(cgpa + rng.random() * 0.35, 3),
            )
        )

    by_id = {s.id: s for s in students}
    interviews: list[Interview] = []
    for company in companies:
        eligible = [
            s for s in students
            if s.cgpa >= company.cgpa_cutoff and s.branch in company.eligible_branches
        ]
        scored: list[tuple[float, Student]] = []
        for s in eligible:
            top_bonus = max(0.0, s.cgpa - company.cgpa_cutoff) * 1.7
            branch_bonus = 0.35 if s.branch in {"CSE", "IT", "AI/DS"} and company.company_type in {"SaaS", "fintech", "premium/product", "startup"} else 0.0
            overlap_bonus = 0.13 * len(s.shortlisted_company_ids)
            mass_noise = rng.random() * (1.4 if company.company_type == "mass recruiter" else 0.9)
            score = top_bonus + branch_bonus + overlap_bonus + mass_noise + s.priority_score * 0.05
            scored.append((score, s))
        scored.sort(key=lambda x: x[0], reverse=True)
        chosen = [s for _, s in scored[: min(company.shortlist_size, len(scored))]]
        # Add a small long-tail component for broad recruiters while keeping deterministic realism.
        if company.company_type in {"mass recruiter", "consulting"} and len(chosen) < company.shortlist_size:
            remaining = [s for s in students if s not in chosen and s.cgpa >= company.cgpa_cutoff - 0.15 and s.branch in company.eligible_branches]
            rng.shuffle(remaining)
            chosen.extend(remaining[: company.shortlist_size - len(chosen)])
        for student in chosen:
            by_id[student.id].shortlisted_company_ids.append(company.id)
            interviews.append(
                Interview(
                    id=f"I{len(interviews) + 1:05d}",
                    student_id=student.id,
                    company_id=company.id,
                    duration=company.interview_duration,
                    priority=company.priority_tier,
                )
            )

    dataset = Dataset(
        seed=seed,
        students=[replace(s, shortlisted_company_ids=sorted(s.shortlisted_company_ids)) for s in students],
        companies=companies,
        panels=panels,
        rooms=_make_rooms(),
        interviews=interviews,
        current_time=day_start(1),
    )
    dataset.events.append(
        EventLog(
            id="E0001",
            timestamp=dataset.current_time,
            event_type="dataset_generated",
            payload={"seed": seed, "students": 800, "companies": 35, "rooms": 20, "interviews": len(interviews)},
            description=f"Generated deterministic dataset with seed {seed}.",
        )
    )
    return dataset

