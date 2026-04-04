from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agents.personalizer import get_personalized_feed
from app.agents.briefing import generate_briefing, answer_followup
from app.agents.story_tracker import track_story
from app.agents.translator import translate_article
from app.agents.summarizer import summarize_article
from app.models.schemas import UserProfile, VideoRequest
from app.services.news_fetcher import fetch_top_headlines, search_news
from app.services.video_studio import generate_news_video

app = FastAPI(title="ET AI News Experience", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "ET AI-Native News Experience API", "version": "1.0.0"}


@app.get("/api/headlines")
def get_headlines(category: str = "business", country: str = "in"):
    articles = fetch_top_headlines(category=category, country=country)
    return {"articles": [a.model_dump() for a in articles]}


@app.get("/api/search")
def search(q: str, page_size: int = 10):
    articles = search_news(q, page_size=page_size)
    return {"articles": [a.model_dump() for a in articles]}


@app.post("/api/personalized-feed")
def personalized_feed(profile: UserProfile):
    return get_personalized_feed(profile)


@app.get("/api/briefing")
def briefing(topic: str):
    return generate_briefing(topic)


class FollowUpRequest(BaseModel):
    topic: str
    context: str
    question: str


@app.post("/api/briefing/followup")
def briefing_followup(req: FollowUpRequest):
    answer = answer_followup(req.topic, req.context, req.question)
    return {"answer": answer}


@app.get("/api/story-arc")
def story_arc(topic: str):
    return track_story(topic)


class TranslateRequest(BaseModel):
    title: str
    content: str
    language: str


@app.post("/api/translate")
def translate(req: TranslateRequest):
    return translate_article(req.title, req.content, req.language)


class SummarizeRequest(BaseModel):
    title: str
    content: str
    style: str = "brief"


@app.post("/api/summarize")
def summarize(req: SummarizeRequest):
    summary = summarize_article(req.title, req.content, req.style)
    return {"summary": summary}


@app.post("/api/video/generate")
def video_generate(req: VideoRequest):
    return generate_news_video(req).model_dump()
