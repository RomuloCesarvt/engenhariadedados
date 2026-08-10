import os

leadsage_path = r"c:\Users\RomuloMeloMouraLeite\.gemini\antigravity\scratch\LeadSage\backend\app"

database_content = """from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, String, Integer, Boolean, JSON

DATABASE_URL = "sqlite+aiosqlite:///./leadsage.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

class DBLead(Base):
    __tablename__ = "leads"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    avatar = Column(String)
    role = Column(String)
    niche = Column(String)
    company = Column(String)
    location = Column(String)
    city = Column(String)
    email = Column(String)
    phone = Column(String)
    whatsapp = Column(Boolean, nullable=True)
    socials = Column(JSON, nullable=True)
    quality_score = Column(Integer)
    verified = Column(Boolean, default=True)
    bio = Column(String, nullable=True)
    ai_summary = Column(String, nullable=True)
    match_intent = Column(String, nullable=True)
    match_location = Column(String, nullable=True)
    match_business = Column(String, nullable=True)
    experience = Column(String, nullable=True)
    opportunityScore = Column(Integer, nullable=True)
    missingDigitalAssets = Column(JSON, nullable=True)
    outreach_status = Column(String, default="Pendente")
    last_contacted_at = Column(String, nullable=True)
    last_message = Column(String, nullable=True)
    match_category = Column(String, nullable=True)
    pipeline_stage = Column(String, default="Novos")

class DBSearchHistory(Base):
    __tablename__ = "search_history"
    
    id = Column(String, primary_key=True, index=True)
    niche = Column(String)
    location = Column(String)
    total_leads = Column(Integer)
    timestamp = Column(String)
    leads_preview = Column(JSON, nullable=True)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
"""

config_content = """import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    APP_NAME: str = "LeadSage AI Prospecting Engine"
    API_PREFIX: str = "/api"
    ENV: str = os.getenv("ENV", "development")
    FIREBASE_CREDENTIALS_PATH: str = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")
    DEFAULT_USER_CREDITS: int = 500
    
    # SMTP Settings
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "")
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "")

settings = Settings()
"""

dispatcher_content = """import uuid
import aiosmtplib
from email.message import EmailMessage
from datetime import datetime
from app.models import DispatchRequest, DispatchResponse
from app.config import settings

class OutreachDispatcher:
    @staticmethod
    async def dispatch_message(req: DispatchRequest, current_credits: int) -> tuple[DispatchResponse, int]:
        dispatch_cost = 2
        if current_credits < dispatch_cost:
            raise ValueError("Créditos insuficientes para realizar o disparo automatizado.")

        remaining = current_credits - dispatch_cost
        dispatch_id = f"disp_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Send Real Email if channel is email
        if req.channel == "email":
            try:
                message = EmailMessage()
                message["From"] = settings.FROM_EMAIL or "no-reply@leadsage.ai"
                message["To"] = req.lead_email
                message["Subject"] = req.subject or "Contato Prospecção"
                message.set_content(req.body)
                
                # Setup SMTP
                smtp_host = settings.SMTP_HOST
                smtp_port = settings.SMTP_PORT
                smtp_user = settings.SMTP_USER
                smtp_pass = settings.SMTP_PASS
                
                if smtp_user and smtp_pass:
                    await aiosmtplib.send(
                        message,
                        hostname=smtp_host,
                        port=smtp_port,
                        start_tls=True,
                        username=smtp_user,
                        password=smtp_pass
                    )
                    status_text = "Enviado via SMTP (Sucesso)"
                else:
                    # Se não houver credencial configurada, ainda simula para não quebrar.
                    status_text = "Simulado (Credenciais SMTP ausentes)"
            except Exception as e:
                status_text = f"Erro no Envio: {str(e)}"
        elif req.channel == "instagram_direct":
            status_text = "Enviado via Instagram Direct Bot (Simulado)"
        elif req.channel == "linkedin_msg":
            status_text = "Enviado via InMail LinkedIn API (Simulado)"
        else:
            status_text = "Enviado via Webhook Integration (Simulado)"

        preview = f"[{req.channel.upper()}] Para: {req.lead_email} | Assunto: {req.subject or 'Contato Prospecção'}"

        response = DispatchResponse(
            dispatch_id=dispatch_id,
            lead_id=req.lead_id,
            channel=req.channel,
            status=status_text,
            delivered_at=now_iso,
            credits_consumed=dispatch_cost,
            remaining_credits=remaining,
            message_preview=preview
        )

        return response, remaining
"""

main_content = """import uuid
from datetime import datetime
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import json

from app.config import settings
from app.database import init_db, get_db, DBLead, DBSearchHistory

from app.models import (
    LeadSearchRequest, LeadSearchResponse, LeadItem, LeadSocialLinks,
    PitchGenerationRequest, PitchGenerationResponse,
    DispatchRequest, DispatchResponse,
    CreditTopUpRequest, UserProfile,
    DemoSiteRequest, DemoSiteResponse
)
from app.leads_engine import LeadsEngine
from app.ai_generator import AIGenerator
from app.dispatcher import OutreachDispatcher
from app.credit_system import check_and_deduct_credits, get_user_balance, add_credits
from app.firebase_config import get_current_user

app = FastAPI(
    title="LeadSage API",
    description="Backend Python para busca de leads com IA, enriquecimento e disparo automatizado.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CURRENT_USER = UserProfile()

@app.on_event("startup")
async def on_startup():
    await init_db()

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "LeadSage AI Prospecting Engine",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/profile", response_model=UserProfile)
async def get_user_profile(user: dict = Depends(get_current_user)):
    uid = user.get("uid")
    balance_data = await get_user_balance(uid)
    CURRENT_USER.credits = balance_data.get("credits", 0)
    return CURRENT_USER

@app.put("/api/profile", response_model=UserProfile)
def update_user_profile(profile: UserProfile):
    global CURRENT_USER
    CURRENT_USER.name = profile.name
    CURRENT_USER.company_name = profile.company_name
    CURRENT_USER.niche_focus = profile.niche_focus
    CURRENT_USER.email = profile.email
    CURRENT_USER.product_description = profile.product_description
    return CURRENT_USER

@app.post("/api/search-leads", response_model=LeadSearchResponse)
async def search_leads(request: Request, req: LeadSearchRequest, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not req.niche or not req.location:
        raise HTTPException(status_code=400, detail="Nicho e localização são obrigatórios.")

    requested_limit = req.limit or 10
    total_cost = requested_limit
    
    uid = user.get("uid")
    remaining_credits = await check_and_deduct_credits(uid, total_cost)
    if remaining_credits is None:
        remaining_credits = 9999

    maps_key = settings.GOOGLE_MAPS_API_KEY

    try:
        leads = await LeadsEngine.search_leads(
            niche=req.niche,
            location=req.location,
            query=req.query or "",
            limit=requested_limit,
            api_key=maps_key
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    search_id = f"sch_{uuid.uuid4().hex[:8]}"

    # Save to SQLite DB
    for lead in leads:
        db_lead = DBLead(
            id=lead.id,
            name=lead.name,
            avatar=lead.avatar,
            role=lead.role,
            niche=lead.niche,
            company=lead.company,
            location=lead.location,
            city=lead.city,
            email=lead.email,
            phone=lead.phone,
            whatsapp=lead.whatsapp,
            socials=lead.socials.dict() if lead.socials else None,
            quality_score=lead.quality_score,
            verified=lead.verified,
            bio=lead.bio,
            ai_summary=lead.ai_summary,
            match_intent=lead.match_intent,
            match_location=lead.match_location,
            match_business=lead.match_business,
            experience=lead.experience,
            opportunityScore=lead.opportunityScore,
            missingDigitalAssets=lead.missingDigitalAssets,
            outreach_status=lead.outreach_status,
            last_contacted_at=lead.last_contacted_at,
            last_message=lead.last_message,
            match_category=lead.match_category,
            pipeline_stage=lead.pipeline_stage
        )
        db.add(db_lead)

    db_history = DBSearchHistory(
        id=search_id,
        niche=req.niche,
        location=req.location,
        total_leads=len(leads),
        timestamp=datetime.now().strftime("%d/%m/%Y %H:%M"),
        leads_preview=[l.name for l in leads[:3]]
    )
    db.add(db_history)
    
    await db.commit()

    return LeadSearchResponse(
        search_id=search_id,
        niche=req.niche,
        location=req.location,
        total_found=len(leads),
        credits_consumed=total_cost,
        remaining_credits=remaining_credits,
        leads=leads,
        timestamp=datetime.now().isoformat()
    )

@app.post("/api/generate-pitch", response_model=PitchGenerationResponse)
async def generate_pitch(request: Request, req: PitchGenerationRequest, user: dict = Depends(get_current_user)):
    gemini_key = settings.GEMINI_API_KEY
    return await AIGenerator.generate_pitch(req, api_key=gemini_key)

@app.post("/api/generate-demo-site", response_model=DemoSiteResponse)
async def generate_demo_site(request: Request, req: DemoSiteRequest, user: dict = Depends(get_current_user)):
    gemini_key = settings.GEMINI_API_KEY
    return await AIGenerator.generate_demo_site(req, api_key=gemini_key)

@app.post("/api/dispatch", response_model=DispatchResponse)
async def dispatch_outreach(req: DispatchRequest, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    uid = user.get("uid")
    balance_data = await get_user_balance(uid)
    current_credits = balance_data.get("credits", 0)

    try:
        response, remaining = await OutreachDispatcher.dispatch_message(req, current_credits)
    except ValueError as e:
        raise HTTPException(status_code=402, detail=str(e))

    # Update lead status in DB
    result = await db.execute(select(DBLead).where(DBLead.id == req.lead_id))
    lead = result.scalar_one_or_none()
    if lead:
        lead.outreach_status = "Enviado"
        lead.last_contacted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lead.last_message = req.body
        await db.commit()

    # Log deduction
    await check_and_deduct_credits(uid, 2)

    return response

@app.get("/api/credits/balance")
async def get_credits_balance(user: dict = Depends(get_current_user)):
    return await get_user_balance(user.get("uid"))

@app.post("/api/credits/topup")
async def topup_credits(req: CreditTopUpRequest, user: dict = Depends(get_current_user)):
    new_balance = await add_credits(user.get("uid"), req.amount, f"Recarga de {req.amount} créditos via {req.payment_method.upper()}")
    return {
        "status": "success",
        "added": req.amount,
        "new_balance": new_balance,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/history")
async def get_search_history(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBSearchHistory).order_by(DBSearchHistory.timestamp.desc()))
    history = result.scalars().all()
    
    out = []
    for h in history:
        out.append({
            "id": h.id,
            "niche": h.niche,
            "location": h.location,
            "total_leads": h.total_leads,
            "timestamp": h.timestamp,
            "leads_preview": h.leads_preview
        })
    return out

@app.get("/api/suggested-niches")
def get_suggested_niches():
    return [
        {"niche": "Farmacêuticos", "icon": "Pill", "count": "1,420+", "avg_score": 96, "locations": ["Botucatu", "São Paulo", "Campinas"]},
        {"niche": "Médicos & Clínicas", "icon": "Stethoscope", "count": "2,850+", "avg_score": 98, "locations": ["Botucatu", "Ribeirão Preto", "Curitiba"]},
        {"niche": "Dentistas & Ortodontia", "icon": "Smile", "count": "1,180+", "avg_score": 94, "locations": ["Botucatu", "Bauru", "Sorocaba"]},
        {"niche": "Corretores de Imóveis", "icon": "Home", "count": "3,400+", "avg_score": 91, "locations": ["Botucatu", "São Paulo", "Santos"]},
        {"niche": "Advogados Empresariais", "icon": "Briefcase", "count": "990+", "avg_score": 95, "locations": ["Botucatu", "São José dos Campos", "Belo Horizonte"]}
    ]
"""

import codecs
def write_file(name, content):
    with codecs.open(os.path.join(leadsage_path, name), 'w', 'utf-8') as f:
        f.write(content)

write_file('database.py', database_content)
write_file('config.py', config_content)
write_file('dispatcher.py', dispatcher_content)
write_file('main.py', main_content)

print("Files updated successfully!")
