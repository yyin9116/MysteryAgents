"""
API endpoints for model configuration management.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

from database import get_db
from models.model_config import (
    ModelConfigCreate,
    ModelConfigExport,
    ModelConfigImport,
    ModelConfigRead,
    ModelConfigTestRequest,
    ModelConfigTestResponse,
    ModelConfigUpdate,
)
from services.model_config_service import (
    ModelConfigConflictError,
    ModelConfigNotFoundError,
    ModelConfigService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/model-configs", tags=["model-configs"])


@router.get("/", response_model=list[ModelConfigRead])
def list_model_configs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    service = ModelConfigService(db)
    return service.list_configs(skip=skip, limit=limit)


@router.get("", response_model=list[ModelConfigRead], include_in_schema=False)
def list_model_configs_legacy(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Legacy alias without trailing slash to avoid redirect-sensitive clients."""
    return list_model_configs(skip=skip, limit=limit, db=db)


@router.post("/", response_model=ModelConfigRead, status_code=201)
def create_model_config(config: ModelConfigCreate, db: Session = Depends(get_db)):
    service = ModelConfigService(db)
    try:
        return service.create_config(config)
    except ModelConfigConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/export", response_model=ModelConfigExport)
def export_model_configs(db: Session = Depends(get_db)):
    service = ModelConfigService(db)
    return service.export_configs()


@router.post("/import", response_model=dict)
def import_model_configs(payload: ModelConfigImport, db: Session = Depends(get_db)):
    service = ModelConfigService(db)
    return service.import_configs(payload)


@router.get("/{config_id}", response_model=ModelConfigRead)
def get_model_config(config_id: str, db: Session = Depends(get_db)):
    service = ModelConfigService(db)
    try:
        return service.get_config(config_id)
    except ModelConfigNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put("/{config_id}", response_model=ModelConfigRead)
def update_model_config(config_id: str, config: ModelConfigUpdate, db: Session = Depends(get_db)):
    service = ModelConfigService(db)
    try:
        return service.update_config(config_id, config)
    except ModelConfigNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ModelConfigConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.delete("/{config_id}", response_model=ModelConfigRead)
def delete_model_config(config_id: str, db: Session = Depends(get_db)):
    service = ModelConfigService(db)
    try:
        return service.delete_config(config_id)
    except ModelConfigNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{config_id}/test", response_model=ModelConfigTestResponse)
def test_model_config(
    config_id: str,
    request: ModelConfigTestRequest,
    db: Session = Depends(get_db),
):
    service = ModelConfigService(db)
    try:
        result = service.test_config(config_id=config_id, prompt=request.prompt)
        return ModelConfigTestResponse(**result)
    except ModelConfigNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Model config test failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
