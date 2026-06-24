from flask import jsonify
from pydantic import BaseModel, ValidationError
from typing import Optional, Tuple


def validate_or_error(schema_cls: type[BaseModel], data: dict) -> Tuple[Optional[BaseModel], Optional[Tuple]]:
    """校验请求数据，成功返回 (model, None)，失败返回 (None, (error_response, 422))"""
    try:
        return schema_cls(**data), None
    except ValidationError as e:
        errors = []
        for err in e.errors():
            field = ".".join(str(loc) for loc in err["loc"])
            errors.append({"field": field, "msg": err["msg"]})
        return None, (jsonify({"error": "validation_error", "detail": errors}), 422)