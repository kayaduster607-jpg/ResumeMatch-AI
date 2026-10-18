from pydantic import BaseModel


class ResumeUploadData(BaseModel):
    resume_id: int
    filename: str
    text_preview: str


class ResumeUploadResponse(BaseModel):
    success: bool = True
    data: ResumeUploadData
