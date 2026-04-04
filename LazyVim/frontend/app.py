import streamlit as st
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.personalizer import get_personalized_feed
from app.agents.briefing import generate_briefing, answer_followup
from app.agents.story_tracker import track_story
from app.agents.translator import translate_article, LANGUAGE_MAP
from app.agents.summarizer import summarize_article
from app.services.news_fetcher import fetch_top_headlines, search_news
from app.services.video_studio import generate_news_video


def format_source_refs(source_ids, sources):
    refs = []
    for source_id in source_ids or []:
        if 1 <= source_id <= len(sources):
            source = sources[source_id - 1]
            label = source.get("source") or "Unknown source"
            refs.append(f"S{source_id} {label}")
    return "Sources: " + ", ".join(refs) if refs else "Sources: none"


def render_confidence(confidence, prefix="Confidence"):
    if not confidence:
        return
    score = confidence.get("score", 0)
    label = str(confidence.get("label", "low")).title()
    reason = confidence.get("reason", "")
    text = f"{prefix}: {label} ({score}/100)"
    if reason:
        text += f" - {reason}"
    st.caption(text)


def item_text(item):
    if isinstance(item, dict):
        return item.get("text", "")
    return str(item)


def item_sources(item):
    if isinstance(item, dict):
        return item.get("source_ids", [])
    return []


st.set_page_config(
    page_title="ET AI News Intelligence",
    page_icon="https://cdn-icons-png.flaticon.com/512/2965/2965879.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CUSTOM CSS - Professional Design System
# ============================================================
st.markdown("""
<style>
    /* --- Import Fonts --- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

    /* --- Root Variables --- */
    :root {
        --bg-primary: #0a0a0f;
        --bg-secondary: #12121a;
        --bg-card: #1a1a28;
        --bg-card-hover: #222236;
        --bg-glass: rgba(255, 255, 255, 0.03);
        --border-color: rgba(255, 255, 255, 0.06);
        --border-accent: rgba(255, 255, 255, 0.1);
        --text-primary: #f0f0f5;
        --text-secondary: #8b8ba3;
        --text-muted: #5a5a72;
        --accent-primary: #6366f1;
        --accent-secondary: #818cf8;
        --accent-glow: rgba(99, 102, 241, 0.15);
        --accent-red: #ef4444;
        --accent-green: #22c55e;
        --accent-amber: #f59e0b;
        --accent-cyan: #06b6d4;
        --gradient-primary: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
        --gradient-card: linear-gradient(145deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%);
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --radius-xl: 20px;
        --shadow-card: 0 4px 24px rgba(0, 0, 0, 0.2);
        --shadow-glow: 0 0 40px rgba(99, 102, 241, 0.08);
        --transition: all 0.2s ease;
    }

    /* --- Global Overrides --- */
    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    [data-testid="stSidebar"] {
        background: var(--bg-secondary) !important;
        border-right: 1px solid var(--border-color) !important;
    }

    [data-testid="stSidebar"] * {
        font-family: 'Inter', sans-serif !important;
    }

    /* --- Page Header --- */
    .page-header {
        padding: 0.5rem 0 1.5rem 0;
        margin-bottom: 1.5rem;
        border-bottom: 1px solid var(--border-color);
    }

    .page-header h1 {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin: 0 0 0.25rem 0;
        background: var(--gradient-primary);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .page-header p {
        font-size: 0.95rem;
        color: var(--text-secondary);
        margin: 0;
        font-weight: 400;
    }

    /* --- Article Card --- */
    .news-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-lg);
        padding: 1.25rem 1.5rem;
        margin-bottom: 0.75rem;
        transition: var(--transition);
        position: relative;
        overflow: hidden;
    }

    .news-card::before {
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 3px;
        background: var(--gradient-primary);
        border-radius: 0 2px 2px 0;
    }

    .news-card:hover {
        background: var(--bg-card-hover);
        border-color: var(--border-accent);
        box-shadow: var(--shadow-glow);
        transform: translateY(-1px);
    }

    .news-card .card-title {
        font-size: 1rem;
        font-weight: 650;
        color: var(--text-primary);
        margin-bottom: 0.35rem;
        line-height: 1.4;
    }

    .news-card .card-meta {
        font-size: 0.78rem;
        color: var(--text-muted);
        margin-bottom: 0.65rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .news-card .card-meta .dot {
        width: 3px;
        height: 3px;
        border-radius: 50%;
        background: var(--text-muted);
        display: inline-block;
    }

    .news-card .card-hook {
        font-size: 0.88rem;
        color: var(--text-secondary);
        line-height: 1.55;
        margin-bottom: 0.6rem;
    }

    /* --- Relevance Badge --- */
    .relevance-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 0.25rem 0.65rem;
        border-radius: 100px;
    }

    .relevance-badge.high {
        background: rgba(34, 197, 94, 0.12);
        color: var(--accent-green);
        border: 1px solid rgba(34, 197, 94, 0.2);
    }

    .relevance-badge.med {
        background: rgba(245, 158, 11, 0.12);
        color: var(--accent-amber);
        border: 1px solid rgba(245, 158, 11, 0.2);
    }

    .relevance-badge.low {
        background: rgba(239, 68, 68, 0.12);
        color: var(--accent-red);
        border: 1px solid rgba(239, 68, 68, 0.2);
    }

    /* --- Briefing Section --- */
    .briefing-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-lg);
        padding: 1.5rem;
        margin: 0.75rem 0;
    }

    .briefing-card.executive {
        border-left: 3px solid var(--accent-primary);
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.06) 0%, var(--bg-card) 100%);
    }

    .briefing-card .section-label {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--accent-secondary);
        margin-bottom: 0.75rem;
    }

    .briefing-card .section-content {
        font-size: 0.92rem;
        color: var(--text-secondary);
        line-height: 1.65;
    }

    /* --- Timeline --- */
    .timeline-item {
        position: relative;
        padding-left: 2rem;
        padding-bottom: 1.25rem;
        margin-left: 0.5rem;
        border-left: 2px solid var(--border-color);
    }

    .timeline-item:last-child {
        border-left: 2px solid transparent;
        padding-bottom: 0;
    }

    .timeline-item::before {
        content: '';
        position: absolute;
        left: -6px;
        top: 4px;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        border: 2px solid var(--accent-primary);
        background: var(--bg-secondary);
    }

    .timeline-item.high::before {
        background: var(--accent-red);
        border-color: var(--accent-red);
        box-shadow: 0 0 8px rgba(239, 68, 68, 0.4);
    }

    .timeline-item.medium::before {
        background: var(--accent-amber);
        border-color: var(--accent-amber);
    }

    .timeline-item .tl-date {
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .timeline-item .tl-event {
        font-size: 0.9rem;
        color: var(--text-secondary);
        margin-top: 0.2rem;
        line-height: 1.5;
    }

    /* --- Stat/Metric Card --- */
    .stat-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-md);
        padding: 1.25rem;
        text-align: center;
    }

    .stat-card .stat-value {
        font-size: 1.75rem;
        font-weight: 800;
        background: var(--gradient-primary);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .stat-card .stat-label {
        font-size: 0.75rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-top: 0.25rem;
    }

    /* --- Player Card --- */
    .player-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-md);
        padding: 1rem 1.25rem;
        margin-bottom: 0.5rem;
        transition: var(--transition);
    }

    .player-card:hover {
        border-color: var(--border-accent);
    }

    .player-card .player-name {
        font-weight: 650;
        color: var(--text-primary);
        font-size: 0.92rem;
    }

    .player-card .player-role {
        font-size: 0.78rem;
        color: var(--text-muted);
    }

    .player-card .player-stance {
        font-size: 0.82rem;
        color: var(--text-secondary);
        margin-top: 0.35rem;
        font-style: italic;
    }

    /* --- Sentiment Chip --- */
    .sentiment-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.6rem 1rem;
        border-radius: var(--radius-md);
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        margin-bottom: 0.5rem;
        width: 100%;
    }

    .sentiment-chip .period {
        font-weight: 600;
        font-size: 0.85rem;
        color: var(--text-primary);
    }

    .sentiment-chip .reason {
        font-size: 0.8rem;
        color: var(--text-muted);
    }

    /* --- Translation Card --- */
    .translation-panel {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-lg);
        padding: 1.5rem;
    }

    .translation-panel .panel-label {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-muted);
        margin-bottom: 0.5rem;
    }

    .translation-panel .panel-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1.35;
    }

    /* --- Key Term Pill --- */
    .key-term {
        display: inline-flex;
        align-items: baseline;
        gap: 0.5rem;
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-md);
        padding: 0.65rem 1rem;
        margin: 0.25rem;
        font-size: 0.85rem;
    }

    .key-term .term-en {
        font-weight: 650;
        color: var(--text-primary);
    }

    .key-term .term-arrow {
        color: var(--text-muted);
    }

    .key-term .term-trans {
        color: var(--accent-secondary);
        font-weight: 500;
    }

    .key-term .term-desc {
        color: var(--text-muted);
        font-size: 0.78rem;
    }

    /* --- Summary Style Card --- */
    .summary-output {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-lg);
        padding: 1.5rem;
        margin: 0.75rem 0;
    }

    .summary-output .summary-label {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--accent-secondary);
        padding: 0.3rem 0.7rem;
        background: var(--accent-glow);
        border-radius: 100px;
        margin-bottom: 0.75rem;
    }

    .summary-output .summary-text {
        font-size: 0.92rem;
        color: var(--text-secondary);
        line-height: 1.65;
    }

    /* --- Section Title --- */
    .section-title {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-muted);
        margin: 1.5rem 0 0.75rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--border-color);
    }

    /* --- Prediction Card --- */
    .prediction-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-md);
        padding: 1rem 1.25rem;
        margin-bottom: 0.5rem;
    }

    .prediction-card .pred-text {
        font-size: 0.9rem;
        font-weight: 500;
        color: var(--text-primary);
        margin-bottom: 0.4rem;
    }

    .prediction-card .pred-meta {
        display: flex;
        gap: 0.75rem;
        font-size: 0.75rem;
    }

    .confidence-dot {
        display: inline-block;
        width: 6px;
        height: 6px;
        border-radius: 50%;
        margin-right: 0.25rem;
        vertical-align: middle;
    }

    .confidence-dot.high { background: var(--accent-green); }
    .confidence-dot.medium { background: var(--accent-amber); }
    .confidence-dot.low { background: var(--accent-red); }

    /* --- Sidebar Styles --- */
    .sidebar-brand {
        padding: 0.5rem 0 1rem 0;
        text-align: center;
    }

    .sidebar-brand h2 {
        font-size: 1.3rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin: 0;
        background: var(--gradient-primary);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .sidebar-brand p {
        font-size: 0.72rem;
        color: var(--text-muted);
        margin: 0.15rem 0 0 0;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .profile-section-label {
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-muted);
        margin: 1rem 0 0.5rem 0;
    }

    /* --- Morning Brief --- */
    .morning-brief {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(139, 92, 246, 0.05) 100%);
        border: 1px solid rgba(99, 102, 241, 0.15);
        border-radius: var(--radius-lg);
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.25rem;
    }

    .morning-brief .brief-label {
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--accent-secondary);
        margin-bottom: 0.5rem;
    }

    .morning-brief .brief-content {
        font-size: 0.92rem;
        color: var(--text-secondary);
        line-height: 1.65;
    }

    /* --- Profile Badge --- */
    .profile-badge {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-md);
        padding: 0.75rem 1rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .profile-badge .badge-role {
        font-weight: 650;
        font-size: 0.88rem;
        color: var(--text-primary);
        text-transform: capitalize;
    }

    .profile-badge .badge-interests {
        font-size: 0.78rem;
        color: var(--text-muted);
    }

    /* --- Empty State --- */
    .empty-state {
        text-align: center;
        padding: 3rem 2rem;
        color: var(--text-muted);
    }

    .empty-state .empty-icon {
        font-size: 2.5rem;
        margin-bottom: 0.75rem;
        opacity: 0.5;
    }

    .empty-state .empty-title {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-secondary);
        margin-bottom: 0.35rem;
    }

    .empty-state .empty-desc {
        font-size: 0.85rem;
        color: var(--text-muted);
    }

    /* --- Follow-up Q&A --- */
    .suggested-question {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-sm);
        padding: 0.5rem 0.85rem;
        font-size: 0.82rem;
        color: var(--text-secondary);
        display: inline-block;
        margin: 0.2rem;
        cursor: pointer;
        transition: var(--transition);
    }

    .suggested-question:hover {
        border-color: var(--accent-primary);
        color: var(--accent-secondary);
    }

    /* --- Divider --- */
    .section-divider {
        height: 1px;
        background: var(--border-color);
        margin: 1.5rem 0;
        border: none;
    }

    /* --- Footer --- */
    .sidebar-footer {
        font-size: 0.72rem;
        color: var(--text-muted);
        padding: 1rem 0;
        text-align: center;
        border-top: 1px solid var(--border-color);
        margin-top: 1rem;
    }

    .sidebar-footer .tech-stack {
        font-size: 0.65rem;
        color: var(--text-muted);
        opacity: 0.7;
        margin-top: 0.25rem;
    }

    /* --- Quick Pick Buttons --- */
    .quick-picks {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
        margin: 0.75rem 0;
    }

    /* --- Source List --- */
    .source-item {
        padding: 0.5rem 0;
        border-bottom: 1px solid var(--border-color);
        font-size: 0.85rem;
    }

    .source-item:last-child {
        border-bottom: none;
    }

    .source-item a {
        color: var(--accent-secondary);
        text-decoration: none;
    }

    .source-item a:hover {
        text-decoration: underline;
    }

    .source-item .source-name {
        color: var(--text-muted);
        font-size: 0.78rem;
    }

    /* --- Contrarian View --- */
    .contrarian-item {
        background: rgba(245, 158, 11, 0.06);
        border: 1px solid rgba(245, 158, 11, 0.12);
        border-radius: var(--radius-md);
        padding: 0.85rem 1rem;
        margin-bottom: 0.5rem;
        font-size: 0.88rem;
        color: var(--text-secondary);
    }

    /* --- Hide Streamlit Defaults --- */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}

</style>
""", unsafe_allow_html=True)

# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.markdown("""
<div class="sidebar-brand">
    <h2>ET News Intelligence</h2>
    <p>AI-Powered Business News</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    ["My Newsroom", "Intelligence Briefing", "Story Arc Tracker", "Vernacular News", "Smart Summarizer", "AI Video Studio"],
    index=0,
    format_func=lambda x: {
        "My Newsroom": "My Newsroom",
        "Intelligence Briefing": "Intelligence Briefing",
        "Story Arc Tracker": "Story Arc Tracker",
        "Vernacular News": "Vernacular News",
        "Smart Summarizer": "Smart Summarizer",
        "AI Video Studio": "AI Video Studio",
    }[x],
)

st.sidebar.markdown('<div class="profile-section-label">Your Profile</div>', unsafe_allow_html=True)
user_name = st.sidebar.text_input("Name", value="Reader", label_visibility="collapsed", placeholder="Your name")
user_role = st.sidebar.selectbox("Role", ["investor", "founder", "student", "professional", "general"], format_func=lambda x: x.title())
user_interests = st.sidebar.multiselect(
    "Interests",
    ["stocks","bollywood", "sports","startups", "technology", "mutual funds", "crypto", "real estate", "banking", "economy", "politics", "global markets"],
    default=["stocks", "technology"],
)

st.sidebar.markdown("""
<div class="sidebar-footer">
    <div>Built for ET AI Hackathon 2026</div>
    <div>Problem Statement 8</div>
    <div class="tech-stack">Groq &middot; Gemini &middot; SerpApi &middot; FFmpeg</div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# PAGE 1: MY NEWSROOM
# ============================================================
if page == "My Newsroom":
    st.markdown("""
    <div class="page-header">
        <h1>My Newsroom</h1>
        <p>Your personalized business intelligence feed, curated by AI</p>
    </div>
    """, unsafe_allow_html=True)

    col_btn, col_profile = st.columns([2, 1])

    with col_btn:
        refresh = st.button("Refresh My Feed", type="primary", use_container_width=True)

    with col_profile:
        st.markdown(f"""
        <div class="profile-badge">
            <div>
                <div class="badge-role">{user_role.title()}</div>
                <div class="badge-interests">{', '.join(user_interests[:4])}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    if refresh:
        with st.spinner("Curating your personalized feed..."):
            from app.models.schemas import UserProfile
            profile = UserProfile(
                name=user_name,
                role=user_role,
                interests=user_interests,
            )
            result = get_personalized_feed(profile)
            st.session_state["feed"] = result

    if "feed" in st.session_state:
        result = st.session_state["feed"]
        feed_sources = result.get("sources", [])

        # Morning Brief
        if result.get("daily_brief"):
            st.markdown(f"""
            <div class="morning-brief">
                <div class="brief-label">Your Morning Brief</div>
                <div class="brief-content">{result["daily_brief"]}</div>
            </div>
            """, unsafe_allow_html=True)
            render_confidence(result.get("confidence"), "Feed confidence")

        # Curated Articles
        st.markdown('<div class="section-title">Curated For You</div>', unsafe_allow_html=True)

        for item in result.get("personalized_feed", []):
            article = item.get("article", {})
            hook = item.get("personalized_hook", "")
            relevance = item.get("relevance", 5)

            rel_class = "high" if relevance >= 8 else "med" if relevance >= 5 else "low"
            rel_label = "High" if relevance >= 8 else "Medium" if relevance >= 5 else "Low"

            source = article.get('source', '')
            date = article.get('published_at', '')[:10]

            st.markdown(f"""
            <div class="news-card">
                <div class="card-title">{article.get('title', 'Untitled')}</div>
                <div class="card-meta">
                    <span>{source}</span>
                    <span class="dot"></span>
                    <span>{date}</span>
                </div>
                <div class="card-hook">{hook}</div>
                <span class="relevance-badge {rel_class}">{rel_label} &middot; {relevance}/10</span>
            </div>
            """, unsafe_allow_html=True)
            st.caption(format_source_refs(item.get("source_ids", []), feed_sources))

            col_a, col_b, col_c, _ = st.columns([1, 1, 1, 2])
            with col_a:
                if article.get("url") and st.button("Read Full", key=f"read_{article.get('title', '')[:30]}", use_container_width=True):
                    st.markdown(f"[Open Article]({article['url']})")
            with col_b:
                if st.button("Summarize", key=f"sum_{article.get('title', '')[:30]}", use_container_width=True):
                    with st.spinner("Summarizing..."):
                        summary = summarize_article(
                            article.get("title", ""),
                            article.get("description", "") + " " + article.get("content", ""),
                            style=user_role if user_role in ["investor", "founder"] else "brief",
                        )
                        st.markdown(f"""
                        <div class="summary-output">
                            <div class="summary-label">Summary</div>
                            <div class="summary-text">{summary}</div>
                        </div>
                        """, unsafe_allow_html=True)

    else:
        # Default headlines
        st.markdown('<div class="section-title">Top Business Headlines</div>', unsafe_allow_html=True)
        with st.spinner("Loading headlines..."):
            articles = fetch_top_headlines(category="business", page_size=8)
            if articles:
                for a in articles:
                    date_str = a.published_at[:10] if a.published_at else ''
                    st.markdown(f"""
                    <div class="news-card">
                        <div class="card-title">{a.title}</div>
                        <div class="card-meta">
                            <span>{a.source}</span>
                            <span class="dot"></span>
                            <span>{date_str}</span>
                        </div>
                        <div class="card-hook">{a.description or ''}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="empty-state">
                    <div class="empty-icon">&#128240;</div>
                    <div class="empty-title">No headlines available</div>
                    <div class="empty-desc">Click "Refresh My Feed" to get AI-curated news</div>
                </div>
                """, unsafe_allow_html=True)


# ============================================================
# PAGE 2: INTELLIGENCE BRIEFING
# ============================================================
elif page == "Intelligence Briefing":
    st.markdown("""
    <div class="page-header">
        <h1>Intelligence Briefing</h1>
        <p>Multiple sources synthesized into one explorable deep briefing</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        topic = st.text_input("Topic", placeholder="e.g. RBI monetary policy, Adani stocks, Union Budget 2026", label_visibility="collapsed")
    with col2:
        generate = st.button("Generate Briefing", type="primary", use_container_width=True)

    # Quick topic picks
    st.markdown('<div class="section-title">Quick Picks</div>', unsafe_allow_html=True)
    qcols = st.columns(5)
    quick_topics = ["Indian Stock Market", "RBI Policy", "AI Startups India", "Union Budget", "Nifty 50"]
    for i, qt in enumerate(quick_topics):
        with qcols[i]:
            if st.button(qt, key=f"qt_{i}", use_container_width=True):
                topic = qt
                generate = True

    if generate and topic:
        with st.spinner(f"Synthesizing intelligence briefing on \"{topic}\"..."):
            result = generate_briefing(topic)
            st.session_state["briefing"] = result
            st.session_state["briefing_topic"] = topic

    if "briefing" in st.session_state:
        result = st.session_state["briefing"]
        briefing = result.get("briefing", {})
        briefing_sources = result.get("sources", [])

        # Stat bar
        st.markdown("<br>", unsafe_allow_html=True)
        stat_cols = st.columns(3)
        with stat_cols[0]:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{result.get('source_count', 0)}</div>
                <div class="stat-label">Sources Analyzed</div>
            </div>
            """, unsafe_allow_html=True)
        with stat_cols[1]:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{len(briefing.get('key_developments', []))}</div>
                <div class="stat-label">Key Developments</div>
            </div>
            """, unsafe_allow_html=True)
        with stat_cols[2]:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{len(briefing.get('what_to_watch', []))}</div>
                <div class="stat-label">Watch Items</div>
            </div>
            """, unsafe_allow_html=True)
        render_confidence(briefing.get("confidence"), "Briefing confidence")

        # Executive Summary
        st.markdown('<div class="section-title">Executive Summary</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="briefing-card executive">
            <div class="section-content">{briefing.get("executive_summary", "")}</div>
        </div>
        """, unsafe_allow_html=True)
        st.caption(format_source_refs(briefing.get("executive_summary_sources", []), briefing_sources))

        # Key Developments & What to Watch
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="section-title">Key Developments</div>', unsafe_allow_html=True)
            for point in briefing.get("key_developments", []):
                st.markdown(f"""
                <div class="briefing-card">
                    <div class="section-content">{item_text(point)}</div>
                </div>
                """, unsafe_allow_html=True)
                st.caption(format_source_refs(item_sources(point), briefing_sources))

        with col2:
            st.markdown('<div class="section-title">What to Watch</div>', unsafe_allow_html=True)
            for item in briefing.get("what_to_watch", []):
                st.markdown(f"""
                <div class="briefing-card">
                    <div class="section-content">{item_text(item)}</div>
                </div>
                """, unsafe_allow_html=True)
                st.caption(format_source_refs(item_sources(item), briefing_sources))

        # Stakeholder Impact
        st.markdown('<div class="section-title">Stakeholder Impact</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="briefing-card">
            <div class="section-content">{briefing.get("stakeholder_impact", "")}</div>
        </div>
        """, unsafe_allow_html=True)
        st.caption(format_source_refs(briefing.get("stakeholder_impact_sources", []), briefing_sources))

        # Market Implications
        st.markdown('<div class="section-title">Market Implications (India)</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="briefing-card" style="border-left: 3px solid var(--accent-amber);">
            <div class="section-content">{briefing.get("market_implications", "")}</div>
        </div>
        """, unsafe_allow_html=True)
        st.caption(format_source_refs(briefing.get("market_implications_sources", []), briefing_sources))

        # Follow-up Q&A
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Ask Follow-up Questions</div>', unsafe_allow_html=True)

        suggested = briefing.get("follow_up_questions", [])
        if suggested:
            for q in suggested:
                st.markdown(f'<span class="suggested-question">{q}</span>', unsafe_allow_html=True)
            st.markdown("<br><br>", unsafe_allow_html=True)

        followup_q = st.text_input("Your question", placeholder="Ask anything about this briefing...", label_visibility="collapsed")
        if st.button("Ask", type="primary") and followup_q:
            with st.spinner("Analyzing..."):
                context = json.dumps(briefing)
                answer = answer_followup(
                    st.session_state.get("briefing_topic", ""),
                    context,
                    followup_q,
                )
                st.markdown(f"""
                <div class="briefing-card">
                    <div class="section-label">Answer</div>
                    <div class="section-content">{answer}</div>
                </div>
                """, unsafe_allow_html=True)

        # Sources
        with st.expander("View Sources"):
            for s in result.get("sources", []):
                st.markdown(f"""
                <div class="source-item">
                    <a href="{s.get('url', '')}" target="_blank">{s.get('title', '')}</a>
                    <span class="source-name"> &mdash; {s.get('source', '')}</span>
                </div>
                """, unsafe_allow_html=True)

    else:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">&#128270;</div>
            <div class="empty-title">Enter a topic to get started</div>
            <div class="empty-desc">We'll synthesize multiple sources into one comprehensive briefing</div>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# PAGE 3: STORY ARC TRACKER
# ============================================================
elif page == "Story Arc Tracker":
    st.markdown("""
    <div class="page-header">
        <h1>Story Arc Tracker</h1>
        <p>Track any business story &mdash; timeline, players, sentiment, predictions</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        topic = st.text_input("Story to track", placeholder="e.g. Reliance Jio, Tata-Air India merger, EV market India", label_visibility="collapsed")
    with col2:
        track = st.button("Track Story", type="primary", use_container_width=True)

    if track and topic:
        with st.spinner(f"Building story arc for \"{topic}\"..."):
            result = track_story(topic)
            st.session_state["story"] = result

    if "story" in st.session_state:
        result = st.session_state["story"]
        arc = result.get("story_arc", {})
        story_sources = result.get("sources", [])

        # Header
        st.markdown(f"### {arc.get('title', result.get('topic', ''))}")

        # Stats
        stat_cols = st.columns(4)
        with stat_cols[0]:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{result.get('article_count', 0)}</div>
                <div class="stat-label">Articles</div>
            </div>
            """, unsafe_allow_html=True)
        with stat_cols[1]:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{len(arc.get('timeline', []))}</div>
                <div class="stat-label">Events</div>
            </div>
            """, unsafe_allow_html=True)
        with stat_cols[2]:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{len(arc.get('key_players', []))}</div>
                <div class="stat-label">Players</div>
            </div>
            """, unsafe_allow_html=True)
        with stat_cols[3]:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{len(arc.get('predictions', []))}</div>
                <div class="stat-label">Predictions</div>
            </div>
            """, unsafe_allow_html=True)
        render_confidence(arc.get("confidence"), "Story confidence")

        # Narrative Summary
        if arc.get("narrative_summary"):
            st.markdown('<div class="section-title">Narrative Summary</div>', unsafe_allow_html=True)
            st.markdown(f"""
            <div class="briefing-card executive">
                <div class="section-content">{arc["narrative_summary"]}</div>
            </div>
            """, unsafe_allow_html=True)
            st.caption(format_source_refs(arc.get("narrative_summary_sources", []), story_sources))

        # Timeline
        st.markdown('<div class="section-title">Timeline</div>', unsafe_allow_html=True)
        timeline_html = ""
        for event in arc.get("timeline", []):
            sig = event.get("significance", "medium")
            timeline_html += f"""
            <div class="timeline-item {sig}">
                <div class="tl-date">{event.get('date', 'N/A')}</div>
                <div class="tl-event">{event.get('event', '')}</div>
            </div>
            """
        st.markdown(timeline_html, unsafe_allow_html=True)
        for event in arc.get("timeline", []):
            st.caption(format_source_refs(event.get("source_ids", []), story_sources))

        # Key Players & Sentiment
        col1, col2 = st.columns(2)

        with col1:
            st.markdown('<div class="section-title">Key Players</div>', unsafe_allow_html=True)
            for player in arc.get("key_players", []):
                st.markdown(f"""
                <div class="player-card">
                    <div class="player-name">{player.get('name', '')}</div>
                    <div class="player-role">{player.get('role', '')}</div>
                    <div class="player-stance">"{player.get('stance', 'N/A')}"</div>
                </div>
                """, unsafe_allow_html=True)
                st.caption(format_source_refs(player.get("source_ids", []), story_sources))

        with col2:
            st.markdown('<div class="section-title">Sentiment Shifts</div>', unsafe_allow_html=True)
            for shift in arc.get("sentiment_shifts", []):
                sentiment = shift.get("sentiment", "neutral")
                emoji = "&#8599;&#65039;" if sentiment == "positive" else "&#8600;&#65039;" if sentiment == "negative" else "&#8594;&#65039;"
                st.markdown(f"""
                <div class="sentiment-chip">
                    <div>
                        <span style="font-size:1.1rem;">{emoji}</span>
                        <span class="period">{shift.get('period', '')} &mdash; {sentiment.title()}</span>
                        <br/>
                        <span class="reason">{shift.get("reason", "")}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.caption(format_source_refs(shift.get("source_ids", []), story_sources))

        # Contrarian Views
        if arc.get("contrarian_views"):
            st.markdown('<div class="section-title">Contrarian Views</div>', unsafe_allow_html=True)
            for view in arc["contrarian_views"]:
                st.markdown(f'<div class="contrarian-item">{view.get("text", view)}</div>', unsafe_allow_html=True)
                if isinstance(view, dict):
                    st.caption(format_source_refs(view.get("source_ids", []), story_sources))

        # Predictions
        st.markdown('<div class="section-title">Predictions</div>', unsafe_allow_html=True)
        for pred in arc.get("predictions", []):
            conf = pred.get("confidence", "medium")
            st.markdown(f"""
            <div class="prediction-card">
                <div class="pred-text">{pred.get('prediction', '')}</div>
                <div class="pred-meta">
                    <span><span class="confidence-dot {conf}"></span> {conf.title()} confidence</span>
                    <span style="color: var(--text-muted);">&middot;</span>
                    <span style="color: var(--text-muted);">{pred.get('timeframe', 'N/A')}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.caption(format_source_refs(pred.get("source_ids", []), story_sources))

    else:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">&#128200;</div>
            <div class="empty-title">Enter a story to track</div>
            <div class="empty-desc">We'll map out the timeline, key players, sentiment, and predictions</div>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# PAGE 4: VERNACULAR NEWS
# ============================================================
elif page == "Vernacular News":
    st.markdown("""
    <div class="page-header">
        <h1>Vernacular Business News</h1>
        <p>Culturally adapted translations &mdash; not literal, but contextual</p>
    </div>
    """, unsafe_allow_html=True)

    source_option = st.radio("Source", ["Top Headlines", "Custom Text"], horizontal=True, label_visibility="collapsed")

    if source_option == "Top Headlines":
        with st.spinner("Loading headlines..."):
            articles = fetch_top_headlines(page_size=5)
            if articles:
                titles = [a.title for a in articles]
                selected_idx = st.selectbox("Select article", range(len(titles)), format_func=lambda i: titles[i], label_visibility="collapsed")
                selected_article = articles[selected_idx]
                title = selected_article.title
                content = (selected_article.description or "") + " " + (selected_article.content or "")
            else:
                st.warning("Could not fetch headlines. Try custom text.")
                title = ""
                content = ""
    else:
        title = st.text_input("Article title", placeholder="Enter article title")
        content = st.text_area("Article content", height=150, placeholder="Paste article content here...")

    target_lang = st.selectbox("Translate to", list(LANGUAGE_MAP.keys()), format_func=lambda x: LANGUAGE_MAP[x])

    if st.button("Translate", type="primary", use_container_width=False) and title and content:
        with st.spinner(f"Translating to {LANGUAGE_MAP[target_lang]}..."):
            result = translate_article(title, content, target_lang)
            st.session_state["translation"] = result

    if "translation" in st.session_state:
        result = st.session_state["translation"]
        trans = result.get("translation", {})

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="translation-panel">
                <div class="panel-label">Original</div>
                <div class="panel-title">{trans.get('original_title', title)}</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="translation-panel" style="border-left: 3px solid var(--accent-primary);">
                <div class="panel-label">{result.get('language_display', '')}</div>
                <div class="panel-title">{trans.get('translated_title', '')}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="briefing-card">
            <div class="section-content">{trans.get("translated_content", "")}</div>
        </div>
        """, unsafe_allow_html=True)

        if trans.get("cultural_notes"):
            st.markdown('<div class="section-title">Cultural Notes</div>', unsafe_allow_html=True)
            st.markdown(f"""
            <div class="briefing-card" style="border-left: 3px solid var(--accent-cyan);">
                <div class="section-content">{trans['cultural_notes']}</div>
            </div>
            """, unsafe_allow_html=True)

        if trans.get("key_terms"):
            st.markdown('<div class="section-title">Key Terms Glossary</div>', unsafe_allow_html=True)
            terms_html = '<div style="display: flex; flex-wrap: wrap;">'
            for term in trans["key_terms"]:
                terms_html += f"""
                <div class="key-term">
                    <span class="term-en">{term.get('english', '')}</span>
                    <span class="term-arrow">&rarr;</span>
                    <span class="term-trans">{term.get('translated', '')}</span>
                    <span class="term-desc">&mdash; {term.get('explanation', '')}</span>
                </div>
                """
            terms_html += '</div>'
            st.markdown(terms_html, unsafe_allow_html=True)

    else:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">&#127760;</div>
            <div class="empty-title">Select an article and language</div>
            <div class="empty-desc">Get culturally adapted translations in 8 Indian languages</div>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# PAGE 5: SMART SUMMARIZER
# ============================================================
elif page == "Smart Summarizer":
    st.markdown("""
    <div class="page-header">
        <h1>Smart Summarizer</h1>
        <p>Same article, different perspective &mdash; tailored to who you are</p>
    </div>
    """, unsafe_allow_html=True)

    source_option = st.radio("Source", ["Search News", "Paste Article"], horizontal=True, label_visibility="collapsed")

    if source_option == "Search News":
        col_search, col_btn = st.columns([3, 1])
        with col_search:
            query = st.text_input("Search", placeholder="e.g. Infosys quarterly results", label_visibility="collapsed")
        with col_btn:
            search_btn = st.button("Search", type="primary", use_container_width=True)

        if search_btn and query:
            with st.spinner("Searching..."):
                results = search_news(query, page_size=5)
                st.session_state["search_results"] = results

        if "search_results" in st.session_state and st.session_state["search_results"]:
            articles = st.session_state["search_results"]
            titles = [a.title for a in articles]
            selected_idx = st.selectbox("Pick an article", range(len(titles)), format_func=lambda i: titles[i])
            selected = articles[selected_idx]
            title = selected.title
            content = (selected.description or "") + " " + (selected.content or "")
        else:
            title = ""
            content = ""
    else:
        title = st.text_input("Article title", placeholder="Enter article title")
        content = st.text_area("Article content", height=200, placeholder="Paste article content here...")

    st.markdown('<div class="section-title">Choose Summary Style</div>', unsafe_allow_html=True)

    style_cols = st.columns(4)
    styles = [
        ("brief", "Brief", "2-3 sentence summary"),
        ("explainer", "Explainer", "Simple, jargon-free"),
        ("investor", "Investor", "Market impact focus"),
        ("founder", "Founder", "Opportunity focus"),
    ]

    for i, (style_key, style_name, style_desc) in enumerate(styles):
        with style_cols[i]:
            if st.button(f"{style_name}\n{style_desc}", key=f"style_{style_key}", use_container_width=True):
                if title and content:
                    with st.spinner(f"Generating {style_name} summary..."):
                        summary = summarize_article(title, content, style=style_key)
                        st.session_state[f"summary_{style_key}"] = summary

    # Display generated summaries
    style_icons = {"brief": "&#128221;", "explainer": "&#127891;", "investor": "&#128176;", "founder": "&#128640;"}
    has_summaries = any(f"summary_{s[0]}" in st.session_state for s in styles)

    if has_summaries:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        for style_key, style_name, _ in styles:
            if f"summary_{style_key}" in st.session_state:
                icon = style_icons.get(style_key, "")
                st.markdown(f"""
                <div class="summary-output">
                    <div class="summary-label">{icon} {style_name}</div>
                    <div class="summary-text">{st.session_state[f"summary_{style_key}"]}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">&#128221;</div>
            <div class="empty-title">Select an article, then pick a style</div>
            <div class="empty-desc">Get the same news from different perspectives</div>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# PAGE 6: AI VIDEO STUDIO
# ============================================================
elif page == "AI Video Studio":
    st.markdown("""
    <div class="page-header">
        <h1>AI News Video Studio</h1>
        <p>Turn a business news story into a short narrated video with source-matched visuals</p>
    </div>
    """, unsafe_allow_html=True)

    source_option = st.radio("Source", ["Search Topic", "Paste Article"], horizontal=True, label_visibility="collapsed")
    duration = st.select_slider("Duration", options=[60, 90, 120], format_func=lambda x: f"{x}s")
    tone = st.selectbox("Tone", ["Breaking News", "Explainer", "Investor Update"])
    captions = st.toggle("Burn captions into video", value=True)

    video_query = ""
    video_title = ""
    video_content = ""

    if source_option == "Search Topic":
        col_search, col_btn = st.columns([3, 1])
        with col_search:
            video_query = st.text_input(
                "Topic",
                placeholder="e.g. RBI policy outlook, Reliance retail strategy, AI startup funding India",
                label_visibility="collapsed",
                key="video_query",
            )
        with col_btn:
            search_btn = st.button("Find Sources", type="primary", use_container_width=True, key="video_search_btn")

        if search_btn and video_query:
            with st.spinner("Fetching related source coverage..."):
                st.session_state["video_search_results"] = search_news(video_query, page_size=5)

        search_results = st.session_state.get("video_search_results", [])
        if search_results:
            st.markdown('<div class="section-title">Source Coverage</div>', unsafe_allow_html=True)
            for idx, article in enumerate(search_results, start=1):
                st.markdown(f"""
                <div class="news-card">
                    <div class="card-title">S{idx}. {article.title}</div>
                    <div class="card-meta">
                        <span>{article.source}</span>
                        <span class="dot"></span>
                        <span>{article.published_at[:10] if article.published_at else ''}</span>
                    </div>
                    <div class="card-hook">{article.description or ''}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-icon">&#127909;</div>
                <div class="empty-title">Search a topic to build a source-backed video</div>
                <div class="empty-desc">We will synthesize related coverage, extract visuals from article URLs, and render a narrated MP4</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        video_title = st.text_input("Article title", placeholder="Enter article title", key="video_title")
        video_content = st.text_area("Article content", height=220, placeholder="Paste article content here...", key="video_content")

    generate_video = st.button("Generate Video", type="primary", use_container_width=True, key="generate_video")

    if generate_video:
        with st.spinner("Generating storyboard, matching visuals, and rendering video..."):
            result = generate_news_video(
                {
                    "query": video_query if source_option == "Search Topic" else "",
                    "title": video_title if source_option == "Paste Article" else "",
                    "content": video_content if source_option == "Paste Article" else "",
                    "duration_seconds": duration,
                    "tone": tone,
                    "include_captions": captions,
                }
            )
            st.session_state["video_result"] = result.model_dump()

    if "video_result" in st.session_state:
        result = st.session_state["video_result"]
        if result.get("status") != "ok":
            st.error(result.get("error", "Video generation failed."))
        else:
            stat_cols = st.columns(4)
            with stat_cols[0]:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-value">{int(round(result.get('duration_seconds', 0)))}</div>
                    <div class="stat-label">Seconds</div>
                </div>
                """, unsafe_allow_html=True)
            with stat_cols[1]:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-value">{result.get('source_count', 0)}</div>
                    <div class="stat-label">Sources Used</div>
                </div>
                """, unsafe_allow_html=True)
            with stat_cols[2]:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-value">{len(result.get('scenes', []))}</div>
                    <div class="stat-label">Scenes</div>
                </div>
                """, unsafe_allow_html=True)
            with stat_cols[3]:
                assignment_count = len([item for item in result.get("visual_assignments", []) if item.get("image_path")])
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-value">{assignment_count}</div>
                    <div class="stat-label">Source Images</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown('<div class="section-title">Preview</div>', unsafe_allow_html=True)
            st.video(result["video_path"])
            with open(result["video_path"], "rb") as video_file:
                st.download_button(
                    "Download MP4",
                    data=video_file.read(),
                    file_name=os.path.basename(result["video_path"]),
                    mime="video/mp4",
                    use_container_width=False,
                )

            with st.expander("Storyboard and visual matches", expanded=False):
                scenes = result.get("scenes", [])
                assignments = {item.get("scene_id"): item for item in result.get("visual_assignments", [])}
                for scene in scenes:
                    assignment = assignments.get(scene.get("scene_id"), {})
                    st.markdown(f"""
                    <div class="briefing-card">
                        <div class="section-label">Scene {scene.get("scene_id")} &middot; {assignment.get("visual_type", "text_card")}</div>
                        <div class="section-content"><strong>{scene.get("title", "")}</strong><br/>{scene.get("narration", "")}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.caption(
                        f"{format_source_refs(scene.get('source_ids', []), result.get('sources', []))} | "
                        f"Visual reason: {assignment.get('reason', 'n/a')}"
                    )

            with st.expander("Source articles", expanded=False):
                for idx, source in enumerate(result.get("sources", []), start=1):
                    st.markdown(f"""
                    <div class="news-card">
                        <div class="card-title">S{idx}. {source.get('title', '')}</div>
                        <div class="card-meta">
                            <span>{source.get('source', '')}</span>
                            <span class="dot"></span>
                            <span>{source.get('published_at', '')[:10]}</span>
                        </div>
                        <div class="card-hook">{source.get('description', '')}</div>
                    </div>
                    """, unsafe_allow_html=True)
