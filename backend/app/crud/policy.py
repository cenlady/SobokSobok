from sqlalchemy import case, or_
from sqlalchemy.orm import Session, selectinload

from app.core.time import korea_now_naive
from app.models.normalized_policy import NormalizedPolicy
from app.models.policy import PolicyAnnouncement, PolicyProgramPage
from app.services.recommend import NEED_TAG_KEYWORDS


def list_policies(db: Session, skip: int = 0, limit: int = 50):
    return (
        db.query(PolicyAnnouncement)
        .filter(PolicyAnnouncement.is_active.is_(True))
        .order_by(PolicyAnnouncement.last_seen_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def list_normalized_policies(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 20,
    q: str | None = None,
    support_type: str | None = None,
    sido: str | None = None,
    category: str | None = None,
    status: str = "available",
    sort: str = "deadline",
):
    query = db.query(NormalizedPolicy).filter(NormalizedPolicy.is_active.is_(True))

    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                NormalizedPolicy.title.ilike(pattern),
                NormalizedPolicy.summary.ilike(pattern),
            )
        )
    if support_type:
        query = query.filter(NormalizedPolicy.support_type == support_type)
    if sido:
        query = query.filter(
            or_(
                NormalizedPolicy.region_scope == "national",
                NormalizedPolicy.sido == sido,
            )
        )

    if category:
        keywords = NEED_TAG_KEYWORDS[category]
        category_conditions = [
            column.ilike(f"%{keyword}%")
            for keyword in keywords
            for column in (
                NormalizedPolicy.title,
                NormalizedPolicy.summary,
                NormalizedPolicy.support_type,
                NormalizedPolicy.support_content,
            )
        ]
        query = query.filter(or_(*category_conditions))

    now = korea_now_naive()
    if status == "available":
        query = query.filter(
            NormalizedPolicy.status.in_(("open", "notice")),
            or_(NormalizedPolicy.apply_end.is_(None), NormalizedPolicy.apply_end >= now),
        )
    elif status != "all":
        query = query.filter(NormalizedPolicy.status == status)
        if status in {"open", "notice"}:
            query = query.filter(
                or_(NormalizedPolicy.apply_end.is_(None), NormalizedPolicy.apply_end >= now),
            )

    if sort == "latest":
        order_by = (
            NormalizedPolicy.created_at.desc(),
            NormalizedPolicy.apply_end.asc().nullslast(),
            NormalizedPolicy.id.asc(),
        )
    else:
        status_priority = case(
            (NormalizedPolicy.status == "open", 0),
            (NormalizedPolicy.status == "notice", 1),
            (NormalizedPolicy.status == "closed", 2),
            else_=3,
        )
        order_by = (
            status_priority.asc(),
            NormalizedPolicy.apply_end.asc().nullslast(),
            NormalizedPolicy.created_at.desc(),
            NormalizedPolicy.id.asc(),
        )

    total = query.order_by(None).count()
    items = query.order_by(*order_by).offset(skip).limit(limit).all()
    return items, total


def get_policy(db: Session, pbanc_sn: int):
    return db.query(PolicyAnnouncement).options(selectinload(PolicyAnnouncement.attachments)).get(pbanc_sn)


def list_program_pages(db: Session, skip: int = 0, limit: int = 50):
    return (
        db.query(PolicyProgramPage)
        .filter(PolicyProgramPage.is_active.is_(True))
        .order_by(PolicyProgramPage.last_seen_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_program_page(db: Session, page_id: int):
    return db.get(PolicyProgramPage, page_id)
