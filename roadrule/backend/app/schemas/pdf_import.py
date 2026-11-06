from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PdfDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    original_filename: str
    sha256_hash: str
    file_size_bytes: int
    page_count: int
    import_status: str
    created_at: datetime
    processed_at: datetime | None
    error_summary: str | None


class PdfJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    status: str
    total_pages: int
    processed_pages: int
    extracted_question_count: int
    review_required_count: int
    failed_item_count: int
    started_at: datetime | None
    completed_at: datetime | None
    diagnostics: list[dict]


class OptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    option_label: str
    option_text: str
    source_page_number: int
    source_location: dict
    display_order: int


class AnswerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    selected_option_id: UUID | None
    raw_answer_text: str | None
    evidence_page_number: int | None
    evidence_location: dict | None
    verification_status: str


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    asset_type: str
    source_page_number: int
    source_location: dict
    sha256_hash: str


class DraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    import_job_id: UUID
    source_order: int
    source_question_number: str
    question_text: str
    category: str | None
    difficulty: str | None
    answer_status: str
    extraction_status: str
    source_page_number: int
    source_location: dict
    created_at: datetime
    options: list[OptionResponse]
    answer: AnswerResponse | None
    assets: list[AssetResponse]


class DocumentPage(BaseModel):
    items: list[PdfDocumentResponse]
    total: int
    page: int
    page_size: int


class DraftPage(BaseModel):
    items: list[DraftResponse]
    total: int
    page: int
    page_size: int
