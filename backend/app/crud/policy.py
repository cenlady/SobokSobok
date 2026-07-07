from sqlalchemy.orm import Session, selectinload

from app.models.policy import PolicyAnnouncement


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
