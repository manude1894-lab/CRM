"""SQLAlchemy model: ClientIdSequence — one running counter per Triam entity (BRD §19).

Client IDs look like TCPL/00001, TMCL/00077. Each entity has its own counter; the row is locked
(SELECT … FOR UPDATE) while the next number is taken, so two clients saved at the same moment can't
get the same ID.
"""
from sqlalchemy import Column, Integer, String

from app.database import Base


class ClientIdSequence(Base):
    __tablename__ = "client_id_sequences"

    entity_code = Column(String(60), primary_key=True)
    last_value = Column(Integer, nullable=False, default=0)
