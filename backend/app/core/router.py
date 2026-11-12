import hashlib
import json
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .access import require_project_member, require_project_role
from .auth import get_current_user, issue_token, password_hash, password_valid
from .database import get_db
from .models import ApiToken, AuditLog, Organization, Personnel, Project, ProjectMember, User, WorkItem

router = APIRouter(tags=["core"])


class LoginIn(BaseModel):
    username: str
    password: str


class UserIn(LoginIn):
    password: str = Field(min_length=12)
    role: str = "viewer"


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=12)


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    client: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    report_title: str | None = Field(default=None, max_length=255)


class ProjectOut(ProjectIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str


class WorkItemIn(BaseModel):
    code: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=500)
    location: str | None = None
    component: str | None = None
    status: Literal["planned", "in_progress", "completed", "pending_acceptance", "rectify"] = "planned"


class WorkItemPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    location: str | None = Field(default=None, max_length=255)
    component: str | None = Field(default=None, max_length=255)
    status: Literal["planned", "in_progress", "completed", "pending_acceptance", "rectify"] | None = None


class WorkItemOut(WorkItemIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str


class WorkItemImportIn(BaseModel):
    items: list[WorkItemIn]


class OrganizationIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    kind: str | None = Field(default=None, max_length=40)


class OrganizationOut(OrganizationIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str


class PersonnelIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    role: str | None = Field(default=None, max_length=120)
    organization_id: str | None = None


class PersonnelOut(PersonnelIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str


@router.post("/auth/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not password_valid(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": issue_token(user), "token_type": "bearer"}


@router.post("/auth/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    token = request.headers["Authorization"].removeprefix("Bearer ")
    session = db.get(ApiToken, hashlib.sha256(token.encode()).hexdigest())
    if session is not None:
        db.delete(session)
        db.commit()
    return {"status": "logged_out"}


@router.post("/auth/change-password")
def change_password(payload: ChangePasswordIn, db: Session = Depends(get_db)):
    actor = get_current_user()
    user = db.get(User, actor.id)
    if user is None:
        raise HTTPException(401, "Authentication required")
    if not password_valid(payload.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")

    user.password_hash = password_hash(payload.new_password)
    for token in db.scalars(select(ApiToken).where(ApiToken.user_id == user.id)).all():
        db.delete(token)
    db.add(
        AuditLog(
            actor_id=user.id,
            action="change_password",
            entity="User",
            entity_id=user.id,
            detail=json.dumps({"relogin": True}, ensure_ascii=False),
        )
    )
    db.commit()
    return {"status": "password_changed", "relogin": True}


@router.post("/users", status_code=201)
def create_user(payload: UserIn, db: Session = Depends(get_db)):
    actor = get_current_user()
    if actor.role != "admin":
        raise HTTPException(403, "Admin required")
    if payload.role not in {"admin", "project_manager", "engineer", "viewer"}:
        raise HTTPException(422, "Invalid role")
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(409, "Username exists")
    user = User(username=payload.username, password_hash=password_hash(payload.password), role=payload.role)
    db.add(user)
    db.flush()
    db.add(AuditLog(actor_id=actor.id, action="create", entity="User", entity_id=user.id))
    db.commit()
    return {"id": user.id, "username": user.username, "role": user.role}


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectIn, db: Session = Depends(get_db)):
    actor = get_current_user()
    if actor.role != "admin":
        raise HTTPException(403, "Admin required")
    project = Project(**payload.model_dump())
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=actor.id, role="project_manager"))
    db.add(AuditLog(project_id=project.id, actor_id=actor.id, action="create", entity="Project", entity_id=project.id))
    db.commit()
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    actor = get_current_user()
    query = select(Project)
    if actor.role != "admin":
        query = query.join(ProjectMember).where(ProjectMember.user_id == actor.id)
    return db.scalars(query.order_by(Project.created_at.desc())).all()


@router.post("/projects/{project_id}/members", status_code=201)
def add_member(project_id: str, user_id: str, role: str, db: Session = Depends(get_db)):
    actor = require_project_role(project_id, {"project_manager"})
    if role not in {"project_manager", "engineer", "viewer"} or db.get(User, user_id) is None:
        raise HTTPException(422, "Invalid user or role")
    if db.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)):
        raise HTTPException(409, "Already a member")
    member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
    db.add(member)
    db.flush()
    db.add(AuditLog(project_id=project_id, actor_id=actor.id, action="add_member", entity="ProjectMember", entity_id=member.id))
    db.commit()
    return {"id": member.id}


@router.post("/projects/{project_id}/work-items", response_model=WorkItemOut, status_code=201)
def create_work_item(project_id: str, payload: WorkItemIn, db: Session = Depends(get_db)):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    if db.scalar(select(WorkItem).where(WorkItem.project_id == project_id, WorkItem.code == payload.code)):
        raise HTTPException(409, "Work item code exists")
    item = WorkItem(project_id=project_id, **payload.model_dump())
    db.add(item)
    db.flush()
    db.add(AuditLog(project_id=project_id, actor_id=actor.id, action="create", entity="WorkItem", entity_id=item.id))
    db.commit()
    return item


@router.get("/projects/{project_id}/work-items", response_model=list[WorkItemOut])
def list_work_items(project_id: str, db: Session = Depends(get_db)):
    require_project_member(project_id)
    return db.scalars(select(WorkItem).where(WorkItem.project_id == project_id).order_by(WorkItem.code)).all()


@router.patch("/projects/{project_id}/work-items/{item_id}", response_model=WorkItemOut)
def update_work_item(project_id: str, item_id: str, payload: WorkItemPatch, db: Session = Depends(get_db)):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    item = db.get(WorkItem, item_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(404, "Work item not found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes or any(value is None for key, value in changes.items() if key in {"name", "status"}):
        raise HTTPException(422, "A valid work item change is required")
    before = {key: getattr(item, key) for key in changes}
    for key, value in changes.items():
        setattr(item, key, value)
    db.add(AuditLog(project_id=project_id, actor_id=actor.id, action="update", entity="WorkItem", entity_id=item.id,
                    detail=json.dumps({"before": before, "after": changes}, ensure_ascii=False)))
    db.commit()
    return item


@router.post("/projects/{project_id}/organizations", response_model=OrganizationOut, status_code=201)
def create_organization(project_id: str, payload: OrganizationIn, db: Session = Depends(get_db)):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    organization = Organization(project_id=project_id, **payload.model_dump())
    db.add(organization)
    db.flush()
    db.add(AuditLog(project_id=project_id, actor_id=actor.id, action="create", entity="Organization", entity_id=organization.id))
    db.commit()
    return organization


@router.get("/projects/{project_id}/organizations", response_model=list[OrganizationOut])
def list_organizations(project_id: str, db: Session = Depends(get_db)):
    require_project_member(project_id)
    return db.scalars(select(Organization).where(Organization.project_id == project_id).order_by(Organization.name)).all()


@router.post("/projects/{project_id}/personnel", response_model=PersonnelOut, status_code=201)
def create_personnel(project_id: str, payload: PersonnelIn, db: Session = Depends(get_db)):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    if payload.organization_id:
        organization = db.get(Organization, payload.organization_id)
        if organization is None or organization.project_id != project_id:
            raise HTTPException(404, "Organization not found in project")
    person = Personnel(project_id=project_id, **payload.model_dump())
    db.add(person)
    db.flush()
    db.add(AuditLog(project_id=project_id, actor_id=actor.id, action="create", entity="Personnel", entity_id=person.id))
    db.commit()
    return person


@router.get("/projects/{project_id}/personnel", response_model=list[PersonnelOut])
def list_personnel(project_id: str, db: Session = Depends(get_db)):
    require_project_member(project_id)
    return db.scalars(select(Personnel).where(Personnel.project_id == project_id).order_by(Personnel.name)).all()


@router.post("/projects/{project_id}/work-items/import-preview")
async def preview_work_items(project_id: str, file: UploadFile = File(...)):
    require_project_role(project_id, {"project_manager", "engineer"})
    from io import BytesIO
    from zipfile import ZipFile, is_zipfile
    from openpyxl import load_workbook

    contents = await file.read(10 * 1024 * 1024 + 1)
    if len(contents) > 10 * 1024 * 1024 or not is_zipfile(BytesIO(contents)):
        raise HTTPException(422, "Expected an XLSX file up to 10 MB")
    try:
        with ZipFile(BytesIO(contents)) as archive:
            if sum(info.file_size for info in archive.infolist()) > 100 * 1024 * 1024:
                raise HTTPException(422, "XLSX expands beyond 100 MB")
        workbook = load_workbook(BytesIO(contents), read_only=True, data_only=True)
        if "DM" not in workbook:
            raise HTTPException(422, "Workbook has no DM sheet")
        rows = []
        for number, row in enumerate(workbook["DM"].iter_rows(min_row=6, values_only=True), start=6):
            if number > 1005:
                raise HTTPException(422, "DM sheet has too many rows")
            if len(row) < 3 or row[0] is None or not row[2]:
                continue
            rows.append({"source_row": number, "code": f"DM-{row[0]}", "name": str(row[2]).strip(),
                         "component": str(row[3]).strip() if len(row) > 3 and row[3] else None,
                         "location": str(row[9]).strip() if len(row) > 9 and row[9] else None})
        workbook.close()
        return {"items": rows}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, "Invalid workbook") from exc


@router.post("/projects/{project_id}/work-items/import", response_model=list[WorkItemOut], status_code=201)
def import_work_items(project_id: str, payload: WorkItemImportIn, db: Session = Depends(get_db)):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    codes = [item.code for item in payload.items]
    if len(codes) != len(set(codes)) or len(codes) > 1000:
        raise HTTPException(422, "Duplicate or too many work item codes")
    existing = set(db.scalars(select(WorkItem.code).where(WorkItem.project_id == project_id, WorkItem.code.in_(codes))))
    if existing:
        raise HTTPException(409, "Work item code exists")
    items = [WorkItem(project_id=project_id, **item.model_dump()) for item in payload.items]
    db.add_all(items)
    db.flush()
    db.add_all([AuditLog(project_id=project_id, actor_id=actor.id, action="import", entity="WorkItem", entity_id=item.id) for item in items])
    db.commit()
    return items
