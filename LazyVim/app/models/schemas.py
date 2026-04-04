from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    name: str = ""
    role: str = "general"
    interests: list[str] = Field(default_factory=list)
    preferred_language: str = "english"


class Article(BaseModel):
    title: str
    description: str = ""
    content: str = ""
    source: str = ""
    url: str = ""
    published_at: str = ""
    image_url: str = ""


class SourceReference(BaseModel):
    source_ids: list[int] = Field(default_factory=list)


class ConfidenceAssessment(BaseModel):
    score: int = 50
    label: str = "medium"
    reason: str = ""


class PersonalizedSelection(BaseModel):
    index: int = 1
    personalized_hook: str = ""
    relevance: int = 5
    source_ids: list[int] = Field(default_factory=list)


class PersonalizedFeedResult(BaseModel):
    selections: list[PersonalizedSelection] = Field(default_factory=list)
    daily_brief: str = ""
    confidence: ConfidenceAssessment = Field(default_factory=ConfidenceAssessment)


class BriefingListItem(BaseModel):
    text: str = ""
    source_ids: list[int] = Field(default_factory=list)


class BriefingResponse(BaseModel):
    executive_summary: str = ""
    executive_summary_sources: list[int] = Field(default_factory=list)
    key_developments: list[BriefingListItem] = Field(default_factory=list)
    stakeholder_impact: str = ""
    stakeholder_impact_sources: list[int] = Field(default_factory=list)
    market_implications: str = ""
    market_implications_sources: list[int] = Field(default_factory=list)
    what_to_watch: list[BriefingListItem] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    confidence: ConfidenceAssessment = Field(default_factory=ConfidenceAssessment)


class TimelineEvent(BaseModel):
    date: str = ""
    event: str = ""
    significance: str = "medium"
    source_ids: list[int] = Field(default_factory=list)


class KeyPlayer(BaseModel):
    name: str = ""
    role: str = ""
    stance: str = ""
    source_ids: list[int] = Field(default_factory=list)


class SentimentShift(BaseModel):
    period: str = ""
    sentiment: str = "neutral"
    reason: str = ""
    source_ids: list[int] = Field(default_factory=list)


class ContrarianView(BaseModel):
    text: str = ""
    source_ids: list[int] = Field(default_factory=list)


class PredictionItem(BaseModel):
    prediction: str = ""
    confidence: str = "medium"
    timeframe: str = ""
    source_ids: list[int] = Field(default_factory=list)


class StoryArcResponse(BaseModel):
    title: str = ""
    timeline: list[TimelineEvent] = Field(default_factory=list)
    key_players: list[KeyPlayer] = Field(default_factory=list)
    sentiment_shifts: list[SentimentShift] = Field(default_factory=list)
    contrarian_views: list[ContrarianView] = Field(default_factory=list)
    predictions: list[PredictionItem] = Field(default_factory=list)
    narrative_summary: str = ""
    narrative_summary_sources: list[int] = Field(default_factory=list)
    confidence: ConfidenceAssessment = Field(default_factory=ConfidenceAssessment)


class TranslationKeyTerm(BaseModel):
    english: str = ""
    translated: str = ""
    explanation: str = ""


class TranslationResponse(BaseModel):
    translated_title: str = ""
    translated_content: str = ""
    cultural_notes: str = ""
    key_terms: list[TranslationKeyTerm] = Field(default_factory=list)


class Briefing(BaseModel):
    topic: str
    summary: str
    key_points: list[str]
    follow_up_questions: list[str]
    sources: list[Article]


class StoryArc(BaseModel):
    topic: str
    timeline: list[dict]
    key_players: list[str]
    sentiment_shifts: list[dict]
    predictions: list[str]


class TranslatedArticle(BaseModel):
    original: Article
    translated_title: str
    translated_content: str
    language: str
    cultural_context: str = ""


class ImageCandidate(BaseModel):
    article_index: int = 1
    source_url: str = ""
    image_url: str = ""
    local_path: str = ""
    origin_type: str = "thumbnail"
    alt_text: str = ""
    width: int = 0
    height: int = 0


class VideoScene(BaseModel):
    scene_id: int = 1
    title: str = ""
    narration: str = ""
    on_screen_text: list[str] = Field(default_factory=list)
    source_ids: list[int] = Field(default_factory=list)
    preferred_visual_type: str = "source_image"
    duration_seconds: float = 8.0


class VideoScript(BaseModel):
    title: str = ""
    intro_hook: str = ""
    scenes: list[VideoScene] = Field(default_factory=list)
    closing_note: str = ""
    source_summary: str = ""


class SceneVisualAssignment(BaseModel):
    scene_id: int = 1
    visual_type: str = "text_card"
    image_path: str = ""
    article_index: int = 0
    score: float = 0.0
    reason: str = ""


class VideoRequest(BaseModel):
    query: str = ""
    title: str = ""
    content: str = ""
    duration_seconds: int = 90
    tone: str = "Breaking News"
    language: str = "english"
    include_captions: bool = True


class VideoGenerationResult(BaseModel):
    title: str = ""
    topic: str = ""
    duration_seconds: float = 0.0
    video_path: str = ""
    audio_path: str = ""
    subtitle_path: str = ""
    working_dir: str = ""
    scenes: list[VideoScene] = Field(default_factory=list)
    visual_assignments: list[SceneVisualAssignment] = Field(default_factory=list)
    sources: list[Article] = Field(default_factory=list)
    source_count: int = 0
    status: str = "error"
    error: str = ""
