"""Typed P1 worker outputs (pydantic v2). The Card schema here is v0 — the
charter's rubric_P2.md narrates it; S2's first reading extracts it at scale.
Spans are chunk-relative character offsets; every field cites or is droppable.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SpanRef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    start: int
    end: int


class Entity(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    kind: str = "other"          # person|org|project|tool|place|work|concept|other
    aliases: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    model_config = ConfigDict(extra="ignore")
    subject: str
    predicate: str
    object: str | None = None
    polarity: int = 1            # +1 asserts, -1 denies
    confidence: float = 0.8
    time: str | None = None
    span: SpanRef | None = None


class Quote(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str
    start: int = -1
    end: int = -1


class Style(BaseModel):
    model_config = ConfigDict(extra="ignore")
    voice: str = ""
    language: str = ""


class CardV0(BaseModel):
    model_config = ConfigDict(extra="ignore")
    entities: list[Entity] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    quotes: list[Quote] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    style: Style = Field(default_factory=Style)
    retelling_candidates: list[str] = Field(default_factory=list)
    notes: str | None = None


class NamedNote(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    note: str = ""


class OntologyDraft(BaseModel):
    """One induction batch's candidates."""
    model_config = ConfigDict(extra="ignore")
    persons: list[NamedNote] = Field(default_factory=list)
    projects: list[NamedNote] = Field(default_factory=list)
    themes: list[NamedNote] = Field(default_factory=list)
    genres: list[NamedNote] = Field(default_factory=list)
    stance_axes: list[NamedNote] = Field(default_factory=list)
    recurring_stories: list[NamedNote] = Field(default_factory=list)
    style_notes: list[str] = Field(default_factory=list)


class OntologyMerged(OntologyDraft):
    """The unified ontology after the merge pass."""
    summary: str = ""


class RubricOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    rubric_md: str
    prior_md: str
