"""Read-only, project-scoped structured context for chat. Never reads OCR."""
import json
from sqlalchemy import select, func
from ..core.component_models import (
    StructuralComponent, Segment, StructureZone, DesignGroup, ComponentAlias,
    RepairScope, ComponentWorkLink, StageDefinition, ComponentStage, ProgressEvent,
)
from .providers import SourceContext, ProviderAnswer
from .constants import NO_SOURCE_ANSWER
from .embeddings import fold_text


def answer_database_question(db, project_id, question, provider):
    components = db.scalars(select(StructuralComponent).where(
        StructuralComponent.project_id == project_id
    ).order_by(StructuralComponent.segment_id, StructuralComponent.canonical_code)).all()
    if not components:
        return ProviderAnswer(text=NO_SOURCE_ANSWER), []
    ids = [row.id for row in components]
    models = [ComponentAlias, RepairScope, ComponentWorkLink, ComponentStage, ProgressEvent]
    related = {}
    for model in models:
        for row in db.scalars(select(model).where(model.component_id.in_(ids))):
            related.setdefault(row.component_id, []).append({
                "table": model.__tablename__,
                **{col.name: getattr(row, col.name) for col in model.__table__.columns
                   if col.name not in {"created_by", "reviewed_by"}},
            })
    text = fold_text(question)
    contexts = []
    for model in [StructureZone, DesignGroup, StageDefinition]:
        rows = db.scalars(select(model).where(model.project_id == project_id)).all()
        contexts.append(SourceContext(len(contexts)+1, json.dumps([
            {col.name: getattr(row, col.name) for col in model.__table__.columns}
            for row in rows], ensure_ascii=False, default=str), model.__tablename__, 1, 0))
    segments = db.scalars(select(Segment).join(StructureZone).where(StructureZone.project_id == project_id)).all()
    contexts.append(SourceContext(len(contexts)+1, json.dumps([
        {"id": row.id, "zone_id": row.zone_id, "number": row.number} for row in segments
    ], ensure_ascii=False), "Phân đoạn", 1, 0))
    # Exact codes take priority; never silently treat a partial context as project totals.
    exact = [row for row in components if fold_text(row.canonical_code) in text]
    selected = exact or components
    for row in selected:
        data = {col.name: getattr(row, col.name) for col in row.__table__.columns
                if col.name != "created_by"}
        data["records"] = related.get(row.id, [])
        contexts.append(SourceContext(len(contexts)+1, json.dumps(data, ensure_ascii=False, default=str),
                                      f"Database · {row.canonical_code} · {row.id}", 1, 0))
    size = sum(len(context.text) for context in contexts)
    if size > 180000:
        return ProviderAnswer(text="Dữ liệu vượt giới hạn một câu trả lời. Anh chọn mã cấu kiện cụ thể để tra cứu chính xác."), []
    answer = provider.answer(question + "\nChỉ dùng database đính kèm. Phân biệt xác minh, thi công và nghiệm thu. Không suy ra nghiệm thu từ thi công; thiếu bản ghi nghiệm thu phải nói chưa có dữ liệu. Ghi rõ mã cấu kiện và ID bản ghi nguồn; không viện dẫn trang PDF hoặc OCR.", contexts)
    return answer, ["Nguồn: database hiện tại của công trình; không sử dụng OCR. Chưa cung cấp bảng nghiệm thu và nhật ký trong ngữ cảnh này."]
