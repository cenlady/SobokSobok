from sqlalchemy.orm import Session, selectinload

from app.models.policy import PolicyAnnouncement, PolicyProgramPage


def list_policies(db: Session, skip: int = 0, limit: int = 50):
    return (
        db.query(PolicyAnnouncement)
        .filter(PolicyAnnouncement.is_active.is_(True))
        .order_by(PolicyAnnouncement.last_seen_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


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
