"""
Automated Job Application Dashboard — FastAPI Backend
Run with: python app.py
"""

import asyncio
import os
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

load_dotenv()

from database import get_db, init_db
from models import Job, CoffeeChat, EmailOutreach, ApplicationAnswer, CompanyPassword, Notification, Resume
from encryption import encrypt_password, decrypt_password

app = FastAPI(title="Job Application Dashboard")
app.mount("/static", StaticFiles(directory="static"), name="static")


# ─── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    await init_db()
    await _seed_application_questions()


async def _seed_application_questions():
    """Insert default application questions if table is empty."""
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ApplicationAnswer))
        if result.scalars().first():
            return  # Already seeded

        defaults = [
            # Personal Info
            ("first_name", "First Name", "Personal Info"),
            ("last_name", "Last Name", "Personal Info"),
            ("phone", "Phone Number", "Personal Info"),
            ("email", "Email Address", "Personal Info"),
            ("address_line1", "Street Address", "Personal Info"),
            ("city", "City", "Personal Info"),
            ("state", "State", "Personal Info"),
            ("zip_code", "ZIP Code", "Personal Info"),
            ("country", "Country", "Personal Info"),
            ("linkedin_url", "LinkedIn URL", "Personal Info"),
            ("github_url", "GitHub URL", "Personal Info"),
            ("website_url", "Personal Website URL", "Personal Info"),
            # Work Authorization
            ("work_authorized", "Are you authorized to work in the US?", "Work Authorization"),
            ("sponsorship_required", "Will you now or in the future require sponsorship?", "Work Authorization"),
            ("visa_type", "Visa Type (if applicable)", "Work Authorization"),
            # Preferences
            ("willing_to_relocate", "Are you willing to relocate?", "Preferences"),
            ("work_arrangement", "Preferred Work Arrangement (Remote/Hybrid/Onsite)", "Preferences"),
            ("desired_salary", "Desired Salary", "Preferences"),
            ("available_start_date", "Available Start Date", "Preferences"),
            ("years_experience", "Years of Experience", "Preferences"),
            # Education
            ("school", "School / University", "Education"),
            ("major", "Major / Degree", "Education"),
            ("graduation_year", "Graduation Year", "Education"),
            ("gpa", "GPA", "Education"),
            # EEO
            ("gender", "Gender (EEO)", "EEO"),
            ("ethnicity", "Ethnicity (EEO)", "EEO"),
            ("veteran_status", "Veteran Status", "EEO"),
            ("disability_status", "Disability Status", "EEO"),
        ]

        for key, label, category in defaults:
            db.add(ApplicationAnswer(question_key=key, question_label=label, category=category))
        await db.commit()


# ─── Root ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse("static/index.html")


# ═══════════════════════════════════════════════════════════════════════════════
# JOBS
# ═══════════════════════════════════════════════════════════════════════════════

class JobCreate(BaseModel):
    company: str
    title: str
    url: Optional[str] = None
    workday_url: Optional[str] = None
    status: str = "to_apply"
    salary: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class JobUpdate(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    workday_url: Optional[str] = None
    status: Optional[str] = None
    salary: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    tailored_resume: Optional[str] = None


@app.get("/api/jobs")
async def list_jobs(status: Optional[str] = None, search: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    q = select(Job).order_by(Job.created_at.desc())
    result = await db.execute(q)
    jobs = result.scalars().all()
    if status:
        jobs = [j for j in jobs if j.status == status]
    if search:
        s = search.lower()
        jobs = [j for j in jobs if s in j.company.lower() or s in j.title.lower()]
    return [_job_dict(j) for j in jobs]


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_dict(job)


@app.post("/api/jobs", status_code=201)
async def create_job(data: JobCreate, db: AsyncSession = Depends(get_db)):
    job = Job(**data.model_dump())
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return _job_dict(job)


@app.put("/api/jobs/{job_id}")
async def update_job(job_id: int, data: JobUpdate, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(job, field, val)
    if data.status == "applied" and not job.applied_at:
        job.applied_at = datetime.utcnow()
    await db.commit()
    await db.refresh(job)
    return _job_dict(job)


@app.delete("/api/jobs/{job_id}", status_code=204)
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    await db.delete(job)
    await db.commit()


def _job_dict(j: Job) -> dict:
    return {
        "id": j.id, "company": j.company, "title": j.title,
        "url": j.url, "workday_url": j.workday_url, "status": j.status,
        "salary": j.salary, "location": j.location, "source": j.source,
        "notes": j.notes, "tailored_resume": j.tailored_resume,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "applied_at": j.applied_at.isoformat() if j.applied_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# COFFEE CHATS
# ═══════════════════════════════════════════════════════════════════════════════

class CoffeeChatCreate(BaseModel):
    name: str
    company: str
    role: Optional[str] = None
    linkedin_url: Optional[str] = None
    status: str = "to_reach_out"
    follow_up_date: Optional[str] = None
    meeting_notes: Optional[str] = None
    next_action: Optional[str] = None


class CoffeeChatUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    linkedin_url: Optional[str] = None
    status: Optional[str] = None
    follow_up_date: Optional[str] = None
    meeting_notes: Optional[str] = None
    next_action: Optional[str] = None


@app.get("/api/coffee-chats")
async def list_coffee_chats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CoffeeChat).order_by(CoffeeChat.created_at.desc()))
    return [_cc_dict(c) for c in result.scalars().all()]


@app.get("/api/coffee-chats/{cc_id}")
async def get_coffee_chat(cc_id: int, db: AsyncSession = Depends(get_db)):
    c = await db.get(CoffeeChat, cc_id)
    if not c:
        raise HTTPException(404, "Not found")
    return _cc_dict(c)


@app.post("/api/coffee-chats", status_code=201)
async def create_coffee_chat(data: CoffeeChatCreate, db: AsyncSession = Depends(get_db)):
    c = CoffeeChat(**data.model_dump())
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return _cc_dict(c)


@app.put("/api/coffee-chats/{cc_id}")
async def update_coffee_chat(cc_id: int, data: CoffeeChatUpdate, db: AsyncSession = Depends(get_db)):
    c = await db.get(CoffeeChat, cc_id)
    if not c:
        raise HTTPException(404, "Not found")
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(c, field, val)
    await db.commit()
    await db.refresh(c)
    return _cc_dict(c)


@app.delete("/api/coffee-chats/{cc_id}", status_code=204)
async def delete_coffee_chat(cc_id: int, db: AsyncSession = Depends(get_db)):
    c = await db.get(CoffeeChat, cc_id)
    if not c:
        raise HTTPException(404, "Not found")
    await db.delete(c)
    await db.commit()


def _cc_dict(c: CoffeeChat) -> dict:
    return {
        "id": c.id, "name": c.name, "company": c.company, "role": c.role,
        "linkedin_url": c.linkedin_url, "status": c.status,
        "follow_up_date": c.follow_up_date, "meeting_notes": c.meeting_notes,
        "next_action": c.next_action,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# EMAIL OUTREACH
# ═══════════════════════════════════════════════════════════════════════════════

class EmailCreate(BaseModel):
    name: str
    company: str
    role: Optional[str] = None
    email: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    status: str = "to_send"
    follow_up_date: Optional[str] = None


class EmailUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    status: Optional[str] = None
    follow_up_date: Optional[str] = None


@app.get("/api/email-outreach")
async def list_emails(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailOutreach).order_by(EmailOutreach.created_at.desc()))
    return [_email_dict(e) for e in result.scalars().all()]


@app.get("/api/email-outreach/{email_id}")
async def get_email(email_id: int, db: AsyncSession = Depends(get_db)):
    e = await db.get(EmailOutreach, email_id)
    if not e:
        raise HTTPException(404, "Not found")
    return _email_dict(e)


@app.post("/api/email-outreach", status_code=201)
async def create_email(data: EmailCreate, db: AsyncSession = Depends(get_db)):
    e = EmailOutreach(**data.model_dump())
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return _email_dict(e)


@app.put("/api/email-outreach/{email_id}")
async def update_email(email_id: int, data: EmailUpdate, db: AsyncSession = Depends(get_db)):
    e = await db.get(EmailOutreach, email_id)
    if not e:
        raise HTTPException(404, "Not found")
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(e, field, val)
    if data.status == "sent" and not e.sent_at:
        e.sent_at = datetime.utcnow()
    await db.commit()
    await db.refresh(e)
    return _email_dict(e)


@app.delete("/api/email-outreach/{email_id}", status_code=204)
async def delete_email(email_id: int, db: AsyncSession = Depends(get_db)):
    e = await db.get(EmailOutreach, email_id)
    if not e:
        raise HTTPException(404, "Not found")
    await db.delete(e)
    await db.commit()


def _email_dict(e: EmailOutreach) -> dict:
    return {
        "id": e.id, "name": e.name, "company": e.company, "role": e.role,
        "email": e.email, "subject": e.subject, "body": e.body,
        "status": e.status, "follow_up_date": e.follow_up_date,
        "sent_at": e.sent_at.isoformat() if e.sent_at else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# APPLICATION PROFILE (QUESTIONS)
# ═══════════════════════════════════════════════════════════════════════════════

class ProfileUpdate(BaseModel):
    answers: dict  # {question_key: answer}


@app.get("/api/profile")
async def get_profile(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ApplicationAnswer).order_by(ApplicationAnswer.id))
    answers = result.scalars().all()
    by_category: dict = {}
    for a in answers:
        by_category.setdefault(a.category, []).append({
            "id": a.id, "key": a.question_key, "label": a.question_label,
            "answer": a.answer, "category": a.category,
        })
    return by_category


@app.put("/api/profile")
async def update_profile(data: ProfileUpdate, db: AsyncSession = Depends(get_db)):
    for key, answer in data.answers.items():
        result = await db.execute(select(ApplicationAnswer).where(ApplicationAnswer.question_key == key))
        row = result.scalars().first()
        if row:
            row.answer = answer
    await db.commit()
    return {"status": "saved"}


# ═══════════════════════════════════════════════════════════════════════════════
# PASSWORDS
# ═══════════════════════════════════════════════════════════════════════════════

class PasswordCreate(BaseModel):
    company_name: str
    workday_url_pattern: Optional[str] = None
    password: str


class PasswordUpdate(BaseModel):
    company_name: Optional[str] = None
    workday_url_pattern: Optional[str] = None
    password: Optional[str] = None


@app.get("/api/passwords")
async def list_passwords(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CompanyPassword).order_by(CompanyPassword.company_name))
    return [_pw_dict(p) for p in result.scalars().all()]


@app.post("/api/passwords", status_code=201)
async def create_password(data: PasswordCreate, db: AsyncSession = Depends(get_db)):
    enc = encrypt_password(data.password)
    p = CompanyPassword(
        company_name=data.company_name,
        workday_url_pattern=data.workday_url_pattern,
        encrypted_password=enc,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _pw_dict(p)


@app.put("/api/passwords/{pw_id}")
async def update_password(pw_id: int, data: PasswordUpdate, db: AsyncSession = Depends(get_db)):
    p = await db.get(CompanyPassword, pw_id)
    if not p:
        raise HTTPException(404, "Not found")
    if data.company_name:
        p.company_name = data.company_name
    if data.workday_url_pattern:
        p.workday_url_pattern = data.workday_url_pattern
    if data.password:
        p.encrypted_password = encrypt_password(data.password)
    await db.commit()
    await db.refresh(p)
    return _pw_dict(p)


@app.delete("/api/passwords/{pw_id}", status_code=204)
async def delete_password(pw_id: int, db: AsyncSession = Depends(get_db)):
    p = await db.get(CompanyPassword, pw_id)
    if not p:
        raise HTTPException(404, "Not found")
    await db.delete(p)
    await db.commit()


def _pw_dict(p: CompanyPassword) -> dict:
    return {
        "id": p.id, "company_name": p.company_name,
        "workday_url_pattern": p.workday_url_pattern,
        # Never expose the actual password — just confirm it exists
        "has_password": bool(p.encrypted_password),
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/notifications")
async def list_notifications(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Notification).order_by(Notification.created_at.desc()).limit(100))
    items = result.scalars().all()
    unread = sum(1 for n in items if not n.read)
    return {
        "unread": unread,
        "notifications": [_notif_dict(n) for n in items],
    }


@app.put("/api/notifications/read-all", status_code=204)
async def mark_all_read(db: AsyncSession = Depends(get_db)):
    await db.execute(update(Notification).values(read=True))
    await db.commit()


@app.put("/api/notifications/{notif_id}/read", status_code=204)
async def mark_read(notif_id: int, db: AsyncSession = Depends(get_db)):
    n = await db.get(Notification, notif_id)
    if n:
        n.read = True
        await db.commit()


def _notif_dict(n: Notification) -> dict:
    return {
        "id": n.id, "title": n.title, "message": n.message,
        "type": n.type, "read": n.read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


async def _add_notification(title: str, message: str, ntype: str = "info"):
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        db.add(Notification(title=title, message=message, type=ntype))
        await db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# RESUME
# ═══════════════════════════════════════════════════════════════════════════════

class ResumeCreate(BaseModel):
    content: str
    is_base: bool = False
    job_id: Optional[int] = None
    label: Optional[str] = None


class TailorRequest(BaseModel):
    job_description: str
    job_id: Optional[int] = None


@app.get("/api/resume")
async def list_resumes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Resume).order_by(Resume.created_at.desc()))
    return [_resume_dict(r) for r in result.scalars().all()]


@app.get("/api/resume/base")
async def get_base_resume(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Resume).where(Resume.is_base == True))
    r = result.scalars().first()
    if not r:
        raise HTTPException(404, "No base resume saved yet")
    return _resume_dict(r)


@app.post("/api/resume", status_code=201)
async def save_resume(data: ResumeCreate, db: AsyncSession = Depends(get_db)):
    if data.is_base:
        # Clear previous base flag
        result = await db.execute(select(Resume).where(Resume.is_base == True))
        for old in result.scalars().all():
            old.is_base = False
    r = Resume(**data.model_dump())
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return _resume_dict(r)


@app.delete("/api/resume/{resume_id}", status_code=204)
async def delete_resume(resume_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.get(Resume, resume_id)
    if not r:
        raise HTTPException(404, "Not found")
    await db.delete(r)
    await db.commit()


@app.post("/api/resume/tailor")
async def tailor_resume(data: TailorRequest, db: AsyncSession = Depends(get_db)):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(400, "ANTHROPIC_API_KEY not set. Add it to your .env file.")

    # Get base resume
    result = await db.execute(select(Resume).where(Resume.is_base == True))
    base = result.scalars().first()
    if not base:
        raise HTTPException(400, "No base resume found. Save your resume first.")

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are an expert resume writer. Tailor the resume below to match the job description.
Optimize for ATS keywords. Preserve all factual information — do NOT invent experience.
Return only the tailored resume text, no commentary.

=== JOB DESCRIPTION ===
{data.job_description}

=== CURRENT RESUME ===
{base.content}
"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    tailored = message.content[0].text

    # Optionally save to job record
    if data.job_id:
        job = await db.get(Job, data.job_id)
        if job:
            job.tailored_resume = tailored
            await db.commit()

    return {"tailored_resume": tailored}


def _resume_dict(r: Resume) -> dict:
    return {
        "id": r.id, "content": r.content, "is_base": r.is_base,
        "job_id": r.job_id, "label": r.label,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# WORKDAY AUTOMATION
# ═══════════════════════════════════════════════════════════════════════════════

class AutomateRequest(BaseModel):
    email: str
    password: str  # one-time provided; will NOT be persisted here


@app.post("/api/automate/{job_id}")
async def automate_job(job_id: int, data: AutomateRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not job.workday_url:
        raise HTTPException(400, "This job has no Workday URL configured.")

    # Load profile answers as flat dict
    result = await db.execute(select(ApplicationAnswer))
    profile = {a.question_key: (a.answer or "") for a in result.scalars().all()}

    # Try to find a stored password for this company if the provided password is empty
    password = data.password
    if not password:
        pw_result = await db.execute(
            select(CompanyPassword).where(
                CompanyPassword.company_name.ilike(f"%{job.company}%")
            )
        )
        pw_row = pw_result.scalars().first()
        if pw_row:
            password = decrypt_password(pw_row.encrypted_password)

    background_tasks.add_task(
        _run_automation_task,
        job_id=job_id,
        workday_url=job.workday_url,
        email=data.email or profile.get("email", ""),
        password=password,
        profile=profile,
    )

    return {"status": "started", "message": "Automation started in background. Check Notifications for updates."}


async def _run_automation_task(job_id: int, workday_url: str, email: str, password: str, profile: dict):
    from automation.workday import run_workday_automation
    await run_workday_automation(
        job_id=job_id,
        workday_url=workday_url,
        email=email,
        password=password,
        profile=profile,
        notify_callback=_add_notification,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# OVERVIEW / STATS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/overview")
async def overview(db: AsyncSession = Depends(get_db)):
    today = datetime.utcnow().date().isoformat()

    jobs_result = await db.execute(select(Job))
    jobs = jobs_result.scalars().all()

    cc_result = await db.execute(select(CoffeeChat))
    chats = cc_result.scalars().all()

    email_result = await db.execute(select(EmailOutreach))
    emails = email_result.scalars().all()

    notif_result = await db.execute(select(Notification).where(Notification.read == False))
    unread_notifs = len(notif_result.scalars().all())

    pipeline = {}
    for s in ["to_apply", "applied", "phone_screen", "interview", "offer", "rejected"]:
        pipeline[s] = sum(1 for j in jobs if j.status == s)

    # Upcoming follow-ups (due today or overdue)
    coffee_followups = [
        _cc_dict(c) for c in chats
        if c.follow_up_date and c.follow_up_date <= today
    ]
    email_followups = [
        _email_dict(e) for e in emails
        if e.follow_up_date and e.follow_up_date <= today
    ]

    return {
        "total_jobs": len(jobs),
        "pipeline": pipeline,
        "total_coffee_chats": len(chats),
        "total_emails": len(emails),
        "unread_notifications": unread_notifs,
        "coffee_followups": coffee_followups[:10],
        "email_followups": email_followups[:10],
    }


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    import socket

    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "localhost"

    local_ip = get_local_ip()
    print(f"\n🚀 Dashboard running!")
    print(f"   Local:   http://localhost:8000")
    print(f"   Network: http://{local_ip}:8000  (use this on your phone)\n")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
