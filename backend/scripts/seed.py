"""
Seeds the database with departments, one user per role, and sample complaints.

Run from the backend/ directory:
    python -m scripts.seed
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import Base, engine, SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.department import Department
from app.schemas.complaint import ComplaintCreate
from app.services.complaint_service import create_complaint
import app.models  # noqa: F401 ensures all models are registered

DEPARTMENTS = [
    ("Electricity Board", "electricity"),
    ("Water Works", "water supply"),
    ("Sanitation Dept", "sanitation"),
    ("Roads & Infrastructure", "road maintenance"),
    ("Police / Public Safety", "public safety"),
    ("Noise Control", "noise complaint"),
    ("Telecom Regulatory", "internet/telecom"),
    ("General Grievance", "other"),
]

USERS = [
    ("Regular User", "user@example.com", "password123", UserRole.user),
    ("Staff Member", "staff@example.com", "password123", UserRole.staff),
    ("Admin User", "admin@example.com", "password123", UserRole.admin),
    ("Management User", "management@example.com", "password123", UserRole.management),
]

SAMPLE_COMPLAINTS = [
    ("Frequent power cuts in Sector 12", "We have had power outages every evening this week for hours at a time.", 45),
    ("No electricity since yesterday", "Entire street has been without power since last night, urgent.", 120),
    ("Streetlight not working", "The streetlight near the park has been off for two weeks.", 15),
    ("Water supply contaminated", "Tap water smells foul and looks discolored, health hazard.", 80),
    ("Low water pressure", "Water pressure has dropped significantly over the past month.", 30),
    ("No water supply for 3 days", "Our area has had zero water supply since Monday.", 200),
    ("Garbage not collected", "Garbage has not been picked up from our lane in over a week.", 25),
    ("Overflowing public dustbin", "The dustbin at the corner is overflowing and attracting pests.", 10),
    ("Open drain causing smell", "An open drain near the market is causing a terrible smell.", 60),
    ("Pothole causing accidents", "A large pothole on Main Road has caused two accidents this month.", 90),
    ("Road not repaired after digging", "Road dug up for pipeline work months ago, still not repaired.", 40),
    ("Broken footpath tiles", "Footpath tiles are broken and dangerous for pedestrians.", 12),
    ("Increased theft in area", "There have been multiple theft incidents reported in our locality.", 70),
    ("No police patrol at night", "We rarely see any police patrol in our area after 10pm.", 35),
    ("Unauthorized construction noise", "Construction work starts at 5am, violating noise regulations.", 20),
    ("Loud music from banquet hall", "Nearby banquet hall plays extremely loud music till midnight regularly.", 18),
    ("Internet outage for a week", "Broadband has been down for a full week with no resolution.", 55),
    ("Mobile network signal issues", "Very poor mobile signal in our building for the last month.", 22),
    ("Illegal parking blocking road", "Cars parked illegally block half the road every day.", 28),
    ("Street dogs causing issues", "Increasing stray dog population is becoming a safety concern.", 33),
    ("Sewage leakage on street", "Sewage has been leaking onto the street for several days.", 50),
    ("No streetlights in entire lane", "The whole lane has no functioning streetlights, unsafe at night.", 42),
    ("Water logging after rain", "Even light rain causes severe water logging on our street.", 65),
    ("Faulty traffic signal", "Traffic signal at the main crossing has been malfunctioning.", 38),
    ("Public park in poor condition", "The public park equipment is broken and unsafe for children.", 27),
]


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print("Seeding departments...")
        dept_objs = {}
        for name, category in DEPARTMENTS:
            existing = db.query(Department).filter(Department.name == name).first()
            if existing:
                dept_objs[category] = existing
                continue
            dept = Department(name=name, category=category)
            db.add(dept)
            db.commit()
            db.refresh(dept)
            dept_objs[category] = dept
        print(f"  {len(dept_objs)} departments ready.")

        print("Seeding users...")
        user_objs = {}
        for name, email, password, role in USERS:
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                user_objs[role] = existing
                continue
            user = User(name=name, email=email, hashed_password=hash_password(password), role=role)
            db.add(user)
            db.commit()
            db.refresh(user)
            user_objs[role] = user
        print(f"  {len(user_objs)} users ready. Login with password123 for any of them.")

        regular_user = user_objs[UserRole.user]

        print("Seeding sample complaints (this runs them through the AI pipeline, may take a while)...")
        for i, (title, description, people_affected) in enumerate(SAMPLE_COMPLAINTS, 1):
            payload = ComplaintCreate(title=title, description=description, people_affected=people_affected)
            complaint = create_complaint(db, payload, regular_user.id)
            print(f"  [{i}/{len(SAMPLE_COMPLAINTS)}] '{title}' -> category={complaint.category}, priority={complaint.priority_score}")

        print("Seeding complete.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
