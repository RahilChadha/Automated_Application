"""
Automated Job Application Dashboard — FastAPI Backend
Run with: python3 app.py
"""

import asyncio
import json
import os
import re
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

load_dotenv()

from database import get_db, init_db
from models import Job, ApplicationAnswer, LoginCredential, AccountCredential, Notification, Resume
from encryption import encrypt_password, decrypt_password

app = FastAPI(title="Job Application Dashboard")
app.mount("/static", StaticFiles(directory="static"), name="static")


# ─── Resume tailor prompt ─────────────────────────────────────────────────────

TAILOR_PROMPT = """Hi, You are a resume fixer agent, whose job is to modify resumes according to the job posting provided below. The things I expect you to do:

1. Take technical skills, skills, and important qualifications that I am looking for to include in my resume if I share the same experiences.
2. Try to match the language of the job posting, Identify key words and wordings and add them to my resume if they match to my resume, while keeping the essence, numbers and size of the points the same. Make sure to include key words in the job postings
3. Remember as a cardinal rule to not make up experiences or add experiences from the job posting if I have never done it before.
4. Get the highest maximum score for ATS from the relevant job posting
5. Give me the full edited resume ready for download, edit should be such it should not exceed more than 1 page
6. Give me a short summary of the edits
7. Hard deadline of 1 page, make sure its always 1 page, drop words and lines if needed

=== JOB POSTING ===
{job_description}

=== TAILORING NOTES FROM ME ===
{notes_for_tailoring}

=== MY BASE RESUME ===
{base_resume}

Return your response structured EXACTLY like this:
---RESUME START---
[Full 1-page tailored resume]
---RESUME END---
---SUMMARY START---
[Brief bullet points summarising the edits made]
---SUMMARY END---"""


def _parse_tailor_response(text: str):
    r = re.search(r'---RESUME START---\n(.*?)\n---RESUME END---', text, re.DOTALL)
    s = re.search(r'---SUMMARY START---\n(.*?)\n---SUMMARY END---', text, re.DOTALL)
    resume = r.group(1).strip() if r else text.strip()
    summary = s.group(1).strip() if s else ""
    return resume, summary


# ─── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    await init_db()
    await _seed_application_questions()


async def _seed_application_questions():
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ApplicationAnswer))
        if result.scalars().first():
            return
        defaults = [
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
            ("work_authorized", "Authorized to work in the US?", "Work Authorization"),
            ("sponsorship_required", "Will require sponsorship?", "Work Authorization"),
            ("visa_type", "Visa Type (if applicable)", "Work Authorization"),
            ("willing_to_relocate", "Willing to relocate?", "Preferences"),
            ("work_arrangement", "Preferred Work Arrangement", "Preferences"),
            ("desired_salary", "Desired Salary", "Preferences"),
            ("available_start_date", "Available Start Date", "Preferences"),
            ("years_experience", "Years of Experience", "Preferences"),
            ("school", "School / University", "Education"),
            ("major", "Major / Degree", "Education"),
            ("graduation_year", "Graduation Year", "Education"),
            ("gpa", "GPA", "Education"),
            ("gender", "Gender (EEO)", "EEO"),
            ("ethnicity", "Ethnicity (EEO)", "EEO"),
            ("veteran_status", "Veteran Status", "EEO"),
            ("disability_status", "Disability Status", "EEO"),
        ]
        for key, label, category in defaults:
            db.add(ApplicationAnswer(question_key=key, question_label=label, category=category))
        await db.commit()


@app.get("/")
async def root():
    return FileResponse("static/index.html")


# ─── Notifications helper ──────────────────────────────────────────────────────

async def _add_notification(title: str, message: str, ntype: str = "info"):
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        db.add(Notification(title=title, message=message, type=ntype))
        await db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# JOBS
# ═══════════════════════════════════════════════════════════════════════════════

class JobCreate(BaseModel):
    company: str
    title: str
    url: Optional[str] = None
    status: str = "to_apply"
    source: Optional[str] = None
    notes: Optional[str] = None
    notes_for_tailoring: Optional[str] = None
    scraped_description: Optional[str] = None


class JobUpdate(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    notes_for_tailoring: Optional[str] = None
    scraped_description: Optional[str] = None


class ScrapeRequest(BaseModel):
    url: str


@app.post("/api/jobs/scrape-url")
async def scrape_job_url(data: ScrapeRequest):
    """Fetch a job posting URL and extract title, company, source, description."""
    import httpx
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(data.url, headers=headers)
        html = resp.text
    except Exception as e:
        raise HTTPException(400, f"Could not fetch URL: {e}")

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    full_text = soup.get_text(separator="\n", strip=True)

    # Detect source from URL
    url_lower = data.url.lower()
    source = "Company Website"
    if "linkedin.com" in url_lower:
        source = "LinkedIn"
    elif "indeed.com" in url_lower:
        source = "Indeed"
    elif "glassdoor.com" in url_lower:
        source = "Glassdoor"
    elif "lever.co" in url_lower:
        source = "Lever"
    elif "greenhouse.io" in url_lower:
        source = "Greenhouse"
    elif "workday" in url_lower:
        source = "Workday"

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                messages=[{"role": "user", "content": f"""Extract from this job posting page text:
1. Job Title
2. Company Name
3. Source/Platform (e.g. LinkedIn, Indeed, or company name if direct)

Return ONLY valid JSON like: {{"title": "...", "company": "...", "source": "..."}}

Page text (first 3000 chars):
{full_text[:3000]}"""}],
            )
            extracted = json.loads(msg.content[0].text)
            return {
                "title": extracted.get("title", ""),
                "company": extracted.get("company", ""),
                "source": extracted.get("source", source),
                "full_description": full_text[:8000],
            }
        except Exception:
            pass

    # Fallback: use page title
    title_tag = soup.find("title")
    page_title = title_tag.get_text().split("|")[0].split("-")[0].strip() if title_tag else ""
    return {
        "title": page_title,
        "company": "",
        "source": source,
        "full_description": full_text[:8000],
    }


@app.get("/api/jobs")
async def list_jobs(status: Optional[str] = None, search: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).order_by(Job.created_at.desc()))
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
async def create_job(data: JobCreate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    job = Job(**data.model_dump())
    db.add(job)
    await db.commit()
    await db.refresh(job)
    # Auto-trigger resume tailoring if description available
    if job.scraped_description and os.getenv("ANTHROPIC_API_KEY"):
        background_tasks.add_task(
            _auto_tailor_resume,
            job.id, job.company, job.title,
            job.scraped_description, job.notes_for_tailoring or ""
        )
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
        "id": j.id, "company": j.company, "title": j.title, "url": j.url,
        "status": j.status, "source": j.source, "notes": j.notes,
        "notes_for_tailoring": j.notes_for_tailoring,
        "has_description": bool(j.scraped_description),
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "applied_at": j.applied_at.isoformat() if j.applied_at else None,
    }


# ─── Auto-tailor in background ────────────────────────────────────────────────

async def _auto_tailor_resume(job_id: int, company: str, title: str, job_description: str, notes: str):
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Resume).where(Resume.is_base == True))
        base = result.scalars().first()
        if not base:
            await _add_notification(
                "Resume Tailor Skipped",
                f"No base resume saved. Go to Resume page and save your base resume first.",
                "warning"
            )
            return
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            prompt = TAILOR_PROMPT.format(
                job_description=job_description[:6000],
                notes_for_tailoring=notes or "None provided",
                base_resume=base.content,
            )
            message = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            resume_content, summary = _parse_tailor_response(message.content[0].text)
            db.add(Resume(
                content=resume_content,
                is_base=False,
                job_id=job_id,
                job_company=company,
                job_title=title,
                label=f"{company} — {title}",
                edit_summary=summary,
            ))
            await db.commit()
            await _add_notification(
                "Resume Tailored",
                f"Resume ready for {company} — {title}. View it on the Resume page.",
                "success"
            )
        except Exception as e:
            await _add_notification("Resume Tailor Failed", f"{company} — {title}: {e}", "error")


# ═══════════════════════════════════════════════════════════════════════════════
# APPLICATION PROFILE
# ═══════════════════════════════════════════════════════════════════════════════

class ProfileUpdate(BaseModel):
    answers: dict


@app.get("/api/profile")
async def get_profile(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ApplicationAnswer).order_by(ApplicationAnswer.id))
    by_cat: dict = {}
    for a in result.scalars().all():
        by_cat.setdefault(a.category, []).append({
            "id": a.id, "key": a.question_key, "label": a.question_label,
            "answer": a.answer, "category": a.category,
        })
    return by_cat


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
# LOGIN CREDENTIALS
# ═══════════════════════════════════════════════════════════════════════════════

class LoginCredCreate(BaseModel):
    label: str
    email: str
    passwords: list[str]   # list of passwords to try in order
    priority: int = 0


class LoginCredUpdate(BaseModel):
    label: Optional[str] = None
    email: Optional[str] = None
    passwords: Optional[list[str]] = None
    priority: Optional[int] = None


@app.get("/api/login-credentials")
async def list_login_creds(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LoginCredential).order_by(LoginCredential.priority, LoginCredential.id))
    return [_lc_dict(c) for c in result.scalars().all()]


@app.post("/api/login-credentials", status_code=201)
async def create_login_cred(data: LoginCredCreate, db: AsyncSession = Depends(get_db)):
    enc = encrypt_password(json.dumps(data.passwords))
    c = LoginCredential(label=data.label, email=data.email, encrypted_passwords_json=enc, priority=data.priority)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return _lc_dict(c)


@app.put("/api/login-credentials/{cred_id}")
async def update_login_cred(cred_id: int, data: LoginCredUpdate, db: AsyncSession = Depends(get_db)):
    c = await db.get(LoginCredential, cred_id)
    if not c:
        raise HTTPException(404, "Not found")
    if data.label is not None:
        c.label = data.label
    if data.email is not None:
        c.email = data.email
    if data.passwords is not None:
        c.encrypted_passwords_json = encrypt_password(json.dumps(data.passwords))
    if data.priority is not None:
        c.priority = data.priority
    await db.commit()
    await db.refresh(c)
    return _lc_dict(c)


@app.delete("/api/login-credentials/{cred_id}", status_code=204)
async def delete_login_cred(cred_id: int, db: AsyncSession = Depends(get_db)):
    c = await db.get(LoginCredential, cred_id)
    if not c:
        raise HTTPException(404, "Not found")
    await db.delete(c)
    await db.commit()


def _lc_dict(c: LoginCredential) -> dict:
    return {
        "id": c.id, "label": c.label, "email": c.email,
        "priority": c.priority, "password_count": len(json.loads(decrypt_password(c.encrypted_passwords_json))),
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ACCOUNT CREDENTIALS
# ═══════════════════════════════════════════════════════════════════════════════

class AccountCredCreate(BaseModel):
    label: str
    email: str
    password: str


class AccountCredUpdate(BaseModel):
    label: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


@app.get("/api/account-credentials")
async def list_account_creds(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AccountCredential).order_by(AccountCredential.id))
    return [_ac_dict(a) for a in result.scalars().all()]


@app.post("/api/account-credentials", status_code=201)
async def create_account_cred(data: AccountCredCreate, db: AsyncSession = Depends(get_db)):
    a = AccountCredential(label=data.label, email=data.email, encrypted_password=encrypt_password(data.password))
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return _ac_dict(a)


@app.put("/api/account-credentials/{cred_id}")
async def update_account_cred(cred_id: int, data: AccountCredUpdate, db: AsyncSession = Depends(get_db)):
    a = await db.get(AccountCredential, cred_id)
    if not a:
        raise HTTPException(404, "Not found")
    if data.label is not None:
        a.label = data.label
    if data.email is not None:
        a.email = data.email
    if data.password is not None:
        a.encrypted_password = encrypt_password(data.password)
    await db.commit()
    await db.refresh(a)
    return _ac_dict(a)


@app.delete("/api/account-credentials/{cred_id}", status_code=204)
async def delete_account_cred(cred_id: int, db: AsyncSession = Depends(get_db)):
    a = await db.get(AccountCredential, cred_id)
    if not a:
        raise HTTPException(404, "Not found")
    await db.delete(a)
    await db.commit()


def _ac_dict(a: AccountCredential) -> dict:
    return {
        "id": a.id, "label": a.label, "email": a.email,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/notifications")
async def list_notifications(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Notification).order_by(Notification.created_at.desc()).limit(100))
    items = result.scalars().all()
    return {
        "unread": sum(1 for n in items if not n.read),
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


# ═══════════════════════════════════════════════════════════════════════════════
# RESUME
# ═══════════════════════════════════════════════════════════════════════════════

class ResumeCreate(BaseModel):
    content: str
    is_base: bool = False
    job_id: Optional[int] = None
    job_company: Optional[str] = None
    job_title: Optional[str] = None
    label: Optional[str] = None


class ManualTailorRequest(BaseModel):
    job_description: str
    notes_for_tailoring: Optional[str] = None
    job_id: Optional[int] = None
    job_company: Optional[str] = None
    job_title: Optional[str] = None


@app.get("/api/resume")
async def list_resumes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Resume).order_by(Resume.created_at.desc()))
    return [_resume_dict(r) for r in result.scalars().all()]


@app.get("/api/resume/{resume_id}")
async def get_resume(resume_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.get(Resume, resume_id)
    if not r:
        raise HTTPException(404, "Not found")
    return _resume_dict(r)


@app.post("/api/resume", status_code=201)
async def save_resume(data: ResumeCreate, db: AsyncSession = Depends(get_db)):
    if data.is_base:
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
async def tailor_resume_manual(data: ManualTailorRequest, db: AsyncSession = Depends(get_db)):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(400, "ANTHROPIC_API_KEY not set in .env")
    result = await db.execute(select(Resume).where(Resume.is_base == True))
    base = result.scalars().first()
    if not base:
        raise HTTPException(400, "No base resume saved yet.")
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    prompt = TAILOR_PROMPT.format(
        job_description=data.job_description[:6000],
        notes_for_tailoring=data.notes_for_tailoring or "None provided",
        base_resume=base.content,
    )
    message = client.messages.create(
        model="claude-opus-4-6", max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    resume_content, summary = _parse_tailor_response(message.content[0].text)
    r = Resume(
        content=resume_content, is_base=False,
        job_id=data.job_id, job_company=data.job_company, job_title=data.job_title,
        label=f"{data.job_company or ''} — {data.job_title or ''}".strip(" —"),
        edit_summary=summary,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return _resume_dict(r)


def _resume_dict(r: Resume) -> dict:
    return {
        "id": r.id, "content": r.content, "is_base": r.is_base,
        "job_id": r.job_id, "job_company": r.job_company, "job_title": r.job_title,
        "label": r.label, "edit_summary": r.edit_summary,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# WORKDAY AUTOMATION
# ═══════════════════════════════════════════════════════════════════════════════

class AutomateRequest(BaseModel):
    login_credential_id: int
    account_credential_id: Optional[int] = None


@app.post("/api/automate/{job_id}")
async def automate_job(job_id: int, data: AutomateRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not job.url:
        raise HTTPException(400, "This job has no URL configured.")

    lc = await db.get(LoginCredential, data.login_credential_id)
    if not lc:
        raise HTTPException(404, "Login credential not found")
    passwords = json.loads(decrypt_password(lc.encrypted_passwords_json))

    ac_email, ac_password = None, None
    if data.account_credential_id:
        ac = await db.get(AccountCredential, data.account_credential_id)
        if ac:
            ac_email = ac.email
            ac_password = decrypt_password(ac.encrypted_password)

    result = await db.execute(select(ApplicationAnswer))
    profile = {a.question_key: (a.answer or "") for a in result.scalars().all()}

    login_creds = [{"email": lc.email, "passwords": passwords}]

    background_tasks.add_task(
        _run_automation_task,
        job_id=job_id, job_url=job.url,
        login_credentials=login_creds,
        account_credential={"email": ac_email, "password": ac_password} if ac_email else None,
        profile=profile,
    )
    return {"status": "started", "message": "Automation started. Watch Notifications for updates."}


async def _run_automation_task(job_id, job_url, login_credentials, account_credential, profile):
    from automation.workday import run_workday_automation
    await run_workday_automation(
        job_id=job_id, job_url=job_url,
        login_credentials=login_credentials,
        account_credential=account_credential,
        profile=profile,
        notify_callback=_add_notification,
    )
    # Update job status to applied after automation
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        job = await db.get(Job, job_id)
        if job and job.status == "to_apply":
            job.status = "applied"
            job.applied_at = datetime.utcnow()
            await db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/overview")
async def overview(db: AsyncSession = Depends(get_db)):
    jobs_result = await db.execute(select(Job))
    jobs = jobs_result.scalars().all()

    notif_result = await db.execute(select(Notification).where(Notification.read == False))
    unread_notifs = len(notif_result.scalars().all())

    pipeline = {}
    for s in ["to_apply", "applied", "round_1", "round_2", "round_3", "offer"]:
        pipeline[s] = sum(1 for j in jobs if j.status == s)

    recent_applied = sorted(
        [j for j in jobs if j.status != "to_apply"],
        key=lambda j: j.applied_at or j.created_at,
        reverse=True
    )[:5]

    return {
        "total_jobs": len(jobs),
        "pipeline": pipeline,
        "unread_notifications": unread_notifs,
        "recent_activity": [_job_dict(j) for j in recent_applied],
    }


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn, socket

    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "localhost"

    print(f"\n  Dashboard running!")
    print(f"  Local:   http://localhost:8000")
    print(f"  Network: http://{get_local_ip()}:8000\n")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
