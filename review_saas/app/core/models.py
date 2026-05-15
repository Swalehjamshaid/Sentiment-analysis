# filename: app/core/models.py

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Float,
)

from sqlalchemy.orm import relationship

from app.core.base import Base


# ==========================================================
# USER MODEL
# ==========================================================

class User(Base):

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(
        String(255),
        nullable=False
    )

    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )

    hashed_password = Column(
        String(512),
        nullable=False
    )

    is_verified = Column(
        Boolean,
        default=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # ======================================================
    # RELATIONSHIPS
    # ======================================================

    verification_tokens = relationship(
        "VerificationToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )


# ==========================================================
# VERIFICATION TOKEN MODEL
# ==========================================================

class VerificationToken(Base):

    __tablename__ = "verification_tokens"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    token = Column(
        String(255),
        unique=True,
        index=True,
        default=lambda: str(uuid4())
    )

    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE"
        )
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # ======================================================
    # RELATIONSHIPS
    # ======================================================

    user = relationship(
        "User",
        back_populates="verification_tokens"
    )


# ==========================================================
# COMPANY MODEL
# ==========================================================

class Company(Base):

    __tablename__ = "companies"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(
        String(255),
        nullable=False
    )

    google_place_id = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )

    address = Column(
        String(512),
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # ======================================================
    # RELATIONSHIPS
    # ======================================================

    reviews = relationship(
        "Review",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    chat_history = relationship(
        "ChatHistory",
        back_populates="company",
        cascade="all, delete-orphan",
    )


# ==========================================================
# REVIEW MODEL
# ==========================================================

class Review(Base):

    __tablename__ = "reviews"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    company_id = Column(
        Integer,
        ForeignKey(
            "companies.id",
            ondelete="CASCADE"
        )
    )

    google_review_id = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )

    author_name = Column(
        String(255),
        nullable=True
    )

    rating = Column(
        Integer,
        nullable=True
    )

    sentiment_score = Column(
        Float,
        nullable=True
    )

    text = Column(
        Text,
        nullable=True
    )

    google_review_time = Column(
        DateTime,
        nullable=True
    )

    first_seen_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    review_likes = Column(
        Integer,
        default=0
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # ======================================================
    # ADVANCED AI ANALYTICS FIELDS
    # ======================================================

    issue_category = Column(
        String(255),
        nullable=True
    )

    emotion = Column(
        String(255),
        nullable=True
    )

    urgency_score = Column(
        Float,
        nullable=True
    )

    ai_summary = Column(
        Text,
        nullable=True
    )

    risk_score = Column(
        Float,
        nullable=True
    )

    topic_cluster = Column(
        Integer,
        nullable=True
    )

    # ======================================================
    # RELATIONSHIPS
    # ======================================================

    company = relationship(
        "Company",
        back_populates="reviews"
    )


# ==========================================================
# CHAT HISTORY MODEL
# ==========================================================

class ChatHistory(Base):

    __tablename__ = "chat_history"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    session_id = Column(
        String(255),
        index=True
    )

    company_id = Column(
        Integer,
        ForeignKey(
            "companies.id",
            ondelete="CASCADE"
        )
    )

    user_message = Column(
        Text
    )

    ai_response = Column(
        Text
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # ======================================================
    # RELATIONSHIPS
    # ======================================================

    company = relationship(
        "Company",
        back_populates="chat_history"
    )
