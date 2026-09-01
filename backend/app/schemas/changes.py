from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.watch import DetailPlanWatchEvent, ProjectWatchEvent


class ChangesResponse(BaseModel):
    """Nya och ändrade objekt i hela datamängden sedan en tidpunkt.

    Händelselistorna begränsas av limit (projekt fyller listan först,
    detaljplaner får resten) medan räkningarna alltid gäller hela
    urvalet — total_events är därför sant även när truncated är true.
    """

    since: datetime = Field(description="Tidpunkten händelserna räknas från, normaliserad till UTC")
    project_events: list[ProjectWatchEvent] = Field(default_factory=list)
    plan_events: list[DetailPlanWatchEvent] = Field(default_factory=list)
    project_new: int = Field(description="Antal projekt som skapats efter since")
    project_changed: int = Field(description="Antal projekt som bara ändrats efter since")
    plan_new: int = Field(description="Antal detaljplaner som skapats efter since")
    plan_changed: int = Field(description="Antal detaljplaner som bara ändrats efter since")
    total_events: int = Field(
        description="Summan av de fyra räkningarna — inte bara de returnerade händelserna"
    )
    truncated: bool = Field(description="true om fler händelser finns än limit")
