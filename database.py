from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import re

db = SQLAlchemy()

def normalize_database_url(url: str) -> str:
    """Normalize postgres:// URLs from Render to postgresql+psycopg2://."""
    if not url:
        return url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


class AnalysisRun(db.Model):
    __tablename__ = 'analysis_runs'

    id = db.Column(db.Integer, primary_key=True)
    search_query = db.Column(db.String(500), nullable=False)
    engine_mode = db.Column(db.String(50), default='Cohere v3.5')
    top_score = db.Column(db.Float, default=0.0)
    top_passage_index = db.Column(db.Integer, default=0)
    verdict = db.Column(db.String(50), default='Moderate')
    missing_entities = db.Column(db.Text, default='')
    copy_advice = db.Column(db.Text, default='')
    total_passages = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    passages = db.relationship('PassageResult', backref='analysis', cascade='all, delete-orphan', lazy=True)


class PassageResult(db.Model):
    __tablename__ = 'passage_results'

    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analysis_runs.id'), nullable=False)
    original_index = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    dense_similarity = db.Column(db.Float, default=0.0)
    initial_dense_rank = db.Column(db.Integer, default=1)
    rerank_score = db.Column(db.Float, default=0.0)
    post_rerank_position = db.Column(db.Integer, default=1)
    rank_shift = db.Column(db.Integer, default=0)  # +2, -1, 0


class Setting(db.Model):
    __tablename__ = 'settings'

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, default='')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
