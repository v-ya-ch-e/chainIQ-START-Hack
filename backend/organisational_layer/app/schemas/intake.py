from pydantic import BaseModel, Field


class IntakeExtractIn(BaseModel):
    source_type: str = Field(default="paste")
    source_text: str = Field(default="")
    note: str | None = None
    request_channel: str | None = None
    file_names: list[str] = Field(default_factory=list)


class IntakeFieldStatusOut(BaseModel):
    status: str
    confidence: float
    reason: str | None = None


class IntakeWarningOut(BaseModel):
    code: str
    severity: str
    message: str


class IntakeExtractOut(BaseModel):
    draft: dict[str, object | None]
    field_status: dict[str, IntakeFieldStatusOut]
    missing_required: list[str]
    warnings: list[IntakeWarningOut]
    extraction_strength: str
