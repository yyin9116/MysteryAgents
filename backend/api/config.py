"""
API endpoints for game configuration export/import.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
logger = logging.getLogger(__name__)

from services.config_export_service import ConfigExportService, GameConfigExport

router = APIRouter()


class ExportRequest(BaseModel):
    """Request to export configuration."""
    name: str
    description: Optional[str] = None
    config: Dict[str, Any]
    agents: List[Dict[str, Any]]
    custom_personalities: Optional[List[Dict[str, Any]]] = None
    format: str = "json"  # "json" or "yaml"


class ImportRequest(BaseModel):
    """Request to import configuration."""
    content: str
    format: str = "json"  # "json" or "yaml"


@router.post("/api/config/export")
async def export_config(request: ExportRequest):
    """
    Export game configuration to JSON or YAML.
    
    Returns:
        Configuration in requested format
    """
    try:
        # Create export object
        export_config = ConfigExportService.export_config(
            config=request.config,
            agents=request.agents,
            custom_personalities=request.custom_personalities,
            name=request.name,
            description=request.description
        )
        
        # Validate
        validation = ConfigExportService.validate_config(export_config)
        if not validation["valid"]:
            return {
                "status": "error",
                "message": "Configuration validation failed",
                "issues": validation["issues"]
            }
        
        # Export to requested format
        if request.format == "yaml":
            content = ConfigExportService.export_to_yaml(export_config)
            media_type = "application/x-yaml"
            filename = f"{request.name.replace(' ', '_')}.yaml"
        else:
            content = ConfigExportService.export_to_json(export_config, pretty=True)
            media_type = "application/json"
            filename = f"{request.name.replace(' ', '_')}.json"
        
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/config/import")
async def import_config(request: ImportRequest):
    """
    Import game configuration from JSON or YAML.
    
    Returns:
        Parsed and validated configuration
    """
    try:
        # Import from requested format
        if request.format == "yaml":
            export_config = ConfigExportService.import_from_yaml(request.content)
        else:
            export_config = ConfigExportService.import_from_json(request.content)
        
        # Validate
        validation = ConfigExportService.validate_config(export_config)
        
        return {
            "status": "success" if validation["valid"] else "warning",
            "config": export_config.dict(exclude_none=True),
            "validation": validation
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/config/validate")
async def validate_config(config: GameConfigExport):
    """
    Validate a game configuration.
    
    Returns:
        Validation results
    """
    try:
        validation = ConfigExportService.validate_config(config)
        return validation
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/config/example")
async def get_example_config(format: str = "json"):
    """
    Get an example configuration.
    
    Args:
        format: "json" or "yaml"
        
    Returns:
        Example configuration
    """
    try:
        example = ConfigExportService.get_example_config()
        
        if format == "yaml":
            content = ConfigExportService.export_to_yaml(example)
            return Response(
                content=content,
                media_type="application/x-yaml"
            )
        else:
            return example.dict(exclude_none=True)
    
    except Exception as e:
        logger.error(f"Failed to get example: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/config/import-file")
async def import_config_file(file: UploadFile = File(...)):
    """
    Import configuration from uploaded file.
    
    Returns:
        Parsed and validated configuration
    """
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Detect format from filename
        format_type = "yaml" if file.filename.endswith(('.yaml', '.yml')) else "json"
        
        # Import
        if format_type == "yaml":
            export_config = ConfigExportService.import_from_yaml(content_str)
        else:
            export_config = ConfigExportService.import_from_json(content_str)
        
        # Validate
        validation = ConfigExportService.validate_config(export_config)
        
        return {
            "status": "success" if validation["valid"] else "warning",
            "config": export_config.dict(exclude_none=True),
            "validation": validation,
            "filename": file.filename
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"File import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
