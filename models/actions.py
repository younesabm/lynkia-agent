from enum import Enum


class Action(str, Enum):
    CREATE_ONE = "CREATE_ONE"
    CREATE_BULK = "CREATE_BULK"
    ADD_COMMENT = "ADD_COMMENT"
    ADD_IMAGE = "ADD_IMAGE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LIST = "LIST"
    SEARCH = "SEARCH"
    GET_IMAGES = "GET_IMAGES"
    HELP = "HELP"
    ERROR = "ERROR"
