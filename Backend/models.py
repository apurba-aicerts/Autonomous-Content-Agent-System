# from core.database import Base, engine, SessionLocal
from sqlalchemy import inspect
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from core.database import Base
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

# ==========================================================
#  MODELS
# ==========================================================

class Brief(Base):
    __tablename__ = "briefs"

    id = Column(Integer, primary_key=True)
    source_type = Column(String(100))
    topic = Column(String(255))
    priority = Column(String(50))

    audience = Column(Text)
    job_to_be_done = Column(Text)
    angle = Column(Text)
    promise = Column(Text)
    cta = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    talking_points = relationship(
        "BriefTalkingPoint",
        back_populates="brief",
        cascade="all, delete-orphan"
    )


class BriefTalkingPoint(Base):
    __tablename__ = "brief_talking_points"

    id = Column(Integer, primary_key=True)
    brief_id = Column(Integer, ForeignKey("briefs.id"))
    talking_point = Column(Text)

    brief = relationship("Brief", back_populates="talking_points")


# ==========================================================
#  CREATE TABLES IF NOT EXISTS
# ==========================================================

# inspector = inspect(engine)

# needed_tables = {
#     "briefs": Brief.__table__,
#     "brief_talking_points": BriefTalkingPoint.__table__,
# }

# for table_name, table_obj in needed_tables.items():
#     if table_name not in inspector.get_table_names():
#         Base.metadata.create_all(bind=engine, tables=[table_obj])
#         print(f"✅ {table_name} table created successfully.")
#     else:
#         print(f"⚠️ {table_name} table already exists.")


# ==========================================================
#  SAVE FUNCTION (STORE 1 BRIEF)
# ==========================================================

def save_brief(item: dict):
    """
    Save a single brief + talking points to database.
    """
    from core.database import SessionLocal  # local import to avoid circular

    db = SessionLocal()

    try:
        brief_data = item.get("brief", {})

        brief = Brief(
            source_type=item.get("source_type"),
            topic=item.get("topic"),
            priority=item.get("priority"),
            audience=brief_data.get("audience"),
            job_to_be_done=brief_data.get("job_to_be_done"),
            angle=brief_data.get("angle"),
            promise=brief_data.get("promise"),
            cta=brief_data.get("cta"),
        )

        db.add(brief)
        db.commit()
        db.refresh(brief)

        # Add talking points
        for tp in brief_data.get("key_talking_points", []):
            db.add(BriefTalkingPoint(
                brief_id=brief.id,
                talking_point=tp
            ))

        db.commit()
        print(f"💾 Saved brief ID {brief.id}")
        return brief.id

    except Exception as e:
        print("❌ DB Error:", e)
        db.rollback()
        return None

    finally:
        db.close()


# ==========================================================
#  SAVE MULTIPLE BRIEFS
# ==========================================================

def save_multiple_briefs(items: list):
    ids = []
    for item in items:
        ids.append(save_brief(item))
    return ids


from sqlalchemy.orm import Session
from datetime import datetime

from core.database import SessionLocal
# from .models import Brief, BriefTalkingPoint

def get_briefs_today(date):
    """
    Fetch all briefs created today, with talking points.
    """
    db: Session = SessionLocal()
    try:
        start = datetime.combine(date, datetime.min.time())
        end = datetime.combine(date, datetime.max.time())

        briefs = (
            db.query(Brief)
            .filter(Brief.created_at >= start)
            .filter(Brief.created_at <= end)
            .all()
        )
        print(f"🔍 Fetched {len(briefs)} briefs for {date.isoformat()}")
        
        results = []
        for b in briefs:
            results.append({
                "id": b.id,
                "source_type": b.source_type,
                "topic": b.topic,
                "priority": b.priority,
                "audience": b.audience,
                "job_to_be_done": b.job_to_be_done,
                "angle": b.angle,
                "promise": b.promise,
                "cta": b.cta,
                "created_at": b.created_at.isoformat(),
                "talking_points": [
                    {"id": tp.id, "talking_point": tp.talking_point}
                    for tp in b.talking_points
                ]
            })

        return results
    finally:
        db.close()

