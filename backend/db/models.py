"""
db/models.py

SQLite/Postgres models for project metadata and standard version tracking.
This is separate from the vector DB — it tracks WHICH standards apply
to WHICH projects, and at WHICH version.

A customer can have:
  - Many projects
  - Each project pins specific editions of standards
  - The same standard (ASHRAE 62.1) at different years for different projects
"""

from datetime import datetime
from sqlalchemy import (
    create_engine, String, Integer, DateTime, Boolean,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column,
    relationship, Session
)


class Base(DeclarativeBase):
    pass


# ── Customer ─────────────────────────────────────────────────────────────────

class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    projects: Mapped[list["Project"]] = relationship(back_populates="customer")
    standards: Mapped[list["UploadedStandard"]] = relationship(back_populates="customer")


# ── Project ───────────────────────────────────────────────────────────────────

class Project(Base):
    """
    A project represents a specific building/job.
    It pins which standard editions apply to that project.
    E.g., "Medical Office 2023" uses ASHRAE 62.1-2019 + IMC 2021
    """
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(1000), default="")
    jurisdiction: Mapped[str] = mapped_column(String(100), default="")  # e.g. "California"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    customer: Mapped["Customer"] = relationship(back_populates="projects")
    # The standards pinned to this project
    pinned_standards: Mapped[list["ProjectStandard"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


# ── Uploaded Standard ─────────────────────────────────────────────────────────

class UploadedStandard(Base):
    """
    A specific PDF uploaded by the customer.
    One row per uploaded file. Indexed into the vector DB.
    """
    __tablename__ = "uploaded_standards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    standard_name: Mapped[str] = mapped_column(String(100))   # "ASHRAE 62.1"
    edition_year: Mapped[int] = mapped_column(Integer)         # 2022
    display_label: Mapped[str] = mapped_column(String(200))    # "ASHRAE 62.1-2022 (Customer Upload)"
    filename: Mapped[str] = mapped_column(String(500))         # original filename
    doc_hash: Mapped[str] = mapped_column(String(64))          # SHA-256 for dedup
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    upload_status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending → processing → ready → error
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str] = mapped_column(String(500), default="")

    customer: Mapped["Customer"] = relationship(back_populates="standards")

    __table_args__ = (
        # Same customer can't upload the same file twice
        UniqueConstraint("customer_id", "doc_hash", name="uq_customer_doc"),
    )


# ── Project ↔ Standard pivot ──────────────────────────────────────────────────

class ProjectStandard(Base):
    """
    Links a project to specific uploaded standards.
    This is how version pinning works:
      Project A → ASHRAE 62.1-2019 (uploaded_standard_id = 'abc')
      Project B → ASHRAE 62.1-2022 (uploaded_standard_id = 'xyz')
    """
    __tablename__ = "project_standards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    uploaded_standard_id: Mapped[str] = mapped_column(ForeignKey("uploaded_standards.id"))
    pinned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str] = mapped_column(String(500), default="")
    # e.g. "Required by AHJ - must use 2019 edition"

    project: Mapped["Project"] = relationship(back_populates="pinned_standards")
    standard: Mapped["UploadedStandard"] = relationship()

    __table_args__ = (
        UniqueConstraint("project_id", "uploaded_standard_id", name="uq_project_standard"),
    )


# ── Chat History ──────────────────────────────────────────────────────────────

class QueryLog(Base):
    """
    Audit log of every question asked and what was cited.
    Useful for debugging, improving the system, and compliance records.
    """
    __tablename__ = "query_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(36))
    project_id: Mapped[str] = mapped_column(String(36))
    question: Mapped[str] = mapped_column(String(2000))
    answer: Mapped[str] = mapped_column(String(10000))
    citations_json: Mapped[str] = mapped_column(String(5000))  # JSON array of citations
    retrieved_chunks: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── DB setup helper ───────────────────────────────────────────────────────────

def create_db(db_url: str = "sqlite:///./hvac_agent.db"):
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return engine
