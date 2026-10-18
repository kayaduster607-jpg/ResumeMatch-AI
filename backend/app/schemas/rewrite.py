from pydantic import BaseModel


class ProjectRewrite(BaseModel):
    project_name: str
    original_text: str
    problems: list[str] = []
    rewritten_text: str
    missing_info_to_add: list[str] = []


class RewriteData(BaseModel):
    rewrites: list[ProjectRewrite] = []


class RewriteResponse(BaseModel):
    success: bool = True
    data: RewriteData
