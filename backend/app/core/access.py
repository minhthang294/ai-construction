from fastapi import HTTPException
from sqlalchemy import select

from .auth import get_current_user
from .database import SessionLocal
from .models import Project, ProjectMember


def require_project_member(project_id: str):
    user = get_current_user()
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if project is None or project.status == Project.DELETED_STATUS:
            raise HTTPException(404, "Project not found")
        if user.role != "admin" and db.scalar(select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)) is None:
            raise HTTPException(404, "Project not found")
    return user


def require_project_role(project_id: str, allowed: set[str]):
    user = require_project_member(project_id)
    if user.role == "admin":
        return user
    with SessionLocal() as db:
        membership = db.scalar(select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user.id))
        if membership is None or membership.role not in allowed:
            raise HTTPException(403, "Insufficient project role")
    return user
