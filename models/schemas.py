from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
from .actions import Action


class InterventionItem(BaseModel):
    type: str
    reference: str


class InterventionData(BaseModel):
    date: str = "TODAY"
    type: str
    reference: str


class BulkInterventionData(BaseModel):
    date: str = "TODAY"
    interventions: List[InterventionItem]


class CommentData(BaseModel):
    reference: str
    commentaire: str


class ImageData(BaseModel):
    reference: str


class UpdateData(BaseModel):
    reference: str
    fields: Dict[str, Any]


class DeleteData(BaseModel):
    reference: str


class ListData(BaseModel):
    scope: str  # TODAY, MOIS, DATE
    date: Optional[str] = None


class SearchData(BaseModel):
    reference: str


class HelpData(BaseModel):
    pass


class ErrorData(BaseModel):
    message: str


class AgentResponse(BaseModel):
    action: Action
    data: Union[
        InterventionData,
        BulkInterventionData,
        CommentData,
        ImageData,
        UpdateData,
        DeleteData,
        ListData,
        SearchData,
        HelpData,
        ErrorData,
        Dict[str, Any],
    ]

    @classmethod
    def create_one(cls, type: str, reference: str, date: str = "TODAY"):
        return cls(
            action=Action.CREATE_ONE,
            data=InterventionData(date=date, type=type, reference=reference),
        )

    @classmethod
    def create_bulk(cls, interventions: List[dict], date: str = "TODAY"):
        items = [InterventionItem(**i) for i in interventions]
        return cls(
            action=Action.CREATE_BULK,
            data=BulkInterventionData(date=date, interventions=items),
        )

    @classmethod
    def add_comment(cls, reference: str, commentaire: str):
        return cls(
            action=Action.ADD_COMMENT,
            data=CommentData(reference=reference, commentaire=commentaire),
        )

    @classmethod
    def add_image(cls, reference: str):
        return cls(action=Action.ADD_IMAGE, data=ImageData(reference=reference))

    @classmethod
    def update(cls, reference: str, fields: Dict[str, Any]):
        return cls(
            action=Action.UPDATE, data=UpdateData(reference=reference, fields=fields)
        )

    @classmethod
    def delete(cls, reference: str):
        return cls(action=Action.DELETE, data=DeleteData(reference=reference))

    @classmethod
    def list_interventions(cls, scope: str, date: Optional[str] = None):
        return cls(action=Action.LIST, data=ListData(scope=scope, date=date))

    @classmethod
    def search(cls, reference: str):
        return cls(action=Action.SEARCH, data=SearchData(reference=reference))

    @classmethod
    def get_images(cls, reference: str):
        return cls(action=Action.GET_IMAGES, data=ImageData(reference=reference))

    @classmethod
    def help(cls):
        return cls(action=Action.HELP, data=HelpData())

    @classmethod
    def error(cls, message: str):
        return cls(action=Action.ERROR, data=ErrorData(message=message))
