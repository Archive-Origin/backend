# Phase 4A.4: Export Functionality - Task 4.4

**Status:** READY FOR IMPLEMENTATION  
**Priority:** MEDIUM  
**Target Completion:** February 7, 2026  
**Depends On:** Phase 4A.3 (Complete)

---

## Overview

Implement export functionality to allow users to export data in multiple formats (CSV, JSON, Excel, PDF). This enables data analysis, reporting, and integration with external systems.

---

## Current State

### Existing Components
- **FastAPI Application** - REST API
- **PostgreSQL Database** - Data persistence
- **Batch Service** - Bulk processing (from Phase 4A.3)

### What's Missing
- Export data models
- Export service with multiple formats
- Export job tracking
- Export endpoints
- Format converters (CSV, JSON, Excel, PDF)
- Scheduled exports

---

## Task 4.4: Implement Export Functionality

### Objectives
1. Create export data models
2. Implement export service
3. Build format converters
4. Create export endpoints
5. Implement scheduled exports

### Implementation Steps

#### Step 1: Export Data Models

**File:** `archiveorigin_backend_api/models/exports.py`

```python
from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class ExportJob(Base):
    """Export job tracking"""
    __tablename__ = "export_jobs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), nullable=False)
    export_type = Column(String(50), nullable=False)  # enrollments, proofs, ledger
    format = Column(String(20), nullable=False)  # csv, json, excel, pdf
    status = Column(String(20), default='pending')  # pending, processing, completed, failed
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    row_count = Column(Integer, default=0)
    filters = Column(JSON, nullable=True)  # Export filters
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    error_message = Column(String(500), nullable=True)
    
    __table_args__ = (
        Index('idx_user_id_status', 'user_id', 'status'),
        Index('idx_status', 'status'),
    )

class ScheduledExport(Base):
    """Scheduled export configuration"""
    __tablename__ = "scheduled_exports"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), nullable=False)
    export_type = Column(String(50), nullable=False)
    format = Column(String(20), nullable=False)
    schedule = Column(String(50), nullable=False)  # daily, weekly, monthly
    email_recipients = Column(JSON, nullable=False)  # List of emails
    active = Column(Boolean, default=True)
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    filters = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_user_id_active', 'user_id', 'active'),
        Index('idx_next_run', 'next_run'),
    )
```

#### Step 2: Export Service

**File:** `archiveorigin_backend_api/services/export_service.py`

```python
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.exports import ExportJob, ScheduledExport
import csv
import json
import io
from typing import List, Dict
import os

class ExportService:
    """Service for export operations"""
    
    @staticmethod
    def create_export_job(
        db: Session,
        user_id: str,
        export_type: str,
        format: str,
        filters: Dict = None
    ) -> ExportJob:
        """Create an export job"""
        export_job = ExportJob(
            user_id=user_id,
            export_type=export_type,
            format=format,
            filters=filters or {}
        )
        db.add(export_job)
        db.commit()
        return export_job
    
    @staticmethod
    def get_export_job(db: Session, export_job_id: str) -> ExportJob:
        """Get an export job"""
        return db.query(ExportJob).filter(
            ExportJob.id == export_job_id
        ).first()
    
    @staticmethod
    def export_to_csv(data: List[Dict]) -> str:
        """Export data to CSV format"""
        if not data:
            return ""
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()
    
    @staticmethod
    def export_to_json(data: List[Dict]) -> str:
        """Export data to JSON format"""
        return json.dumps(data, indent=2, default=str)
    
    @staticmethod
    def export_to_excel(data: List[Dict]) -> bytes:
        """Export data to Excel format"""
        try:
            import openpyxl
            from openpyxl.utils import get_column_letter
            
            wb = openpyxl.Workbook()
            ws = wb.active
            
            if not data:
                return wb.save(io.BytesIO())
            
            # Write headers
            headers = list(data[0].keys())
            for col_num, header in enumerate(headers, 1):
                ws.cell(row=1, column=col_num, value=header)
            
            # Write data
            for row_num, row_data in enumerate(data, 2):
                for col_num, header in enumerate(headers, 1):
                    ws.cell(row=row_num, column=col_num, value=row_data.get(header))
            
            # Auto-adjust column widths
            for col_num, header in enumerate(headers, 1):
                ws.column_dimensions[get_column_letter(col_num)].width = 15
            
            output = io.BytesIO()
            wb.save(output)
            return output.getvalue()
        except ImportError:
            raise Exception("openpyxl not installed")
    
    @staticmethod
    def export_to_pdf(data: List[Dict]) -> bytes:
        """Export data to PDF format"""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
            
            output = io.BytesIO()
            doc = SimpleDocTemplate(output, pagesize=landscape(letter))
            
            if not data:
                doc.build([])
                return output.getvalue()
            
            # Prepare table data
            headers = list(data[0].keys())
            table_data = [headers]
            for row in data:
                table_data.append([str(row.get(h, '')) for h in headers])
            
            # Create table
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 14),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            doc.build([table])
            return output.getvalue()
        except ImportError:
            raise Exception("reportlab not installed")
    
    @staticmethod
    async def process_export_job(
        db: Session,
        export_job_id: str,
        data_fetcher
    ):
        """Process an export job"""
        export_job = ExportService.get_export_job(db, export_job_id)
        if not export_job:
            return
        
        export_job.status = 'processing'
        export_job.started_at = datetime.utcnow()
        db.commit()
        
        try:
            # Fetch data
            data = await data_fetcher(export_job.filters)
            export_job.row_count = len(data)
            
            # Convert to requested format
            if export_job.format == 'csv':
                content = ExportService.export_to_csv(data)
                file_ext = 'csv'
            elif export_job.format == 'json':
                content = ExportService.export_to_json(data)
                file_ext = 'json'
            elif export_job.format == 'excel':
                content = ExportService.export_to_excel(data)
                file_ext = 'xlsx'
            elif export_job.format == 'pdf':
                content = ExportService.export_to_pdf(data)
                file_ext = 'pdf'
            else:
                raise ValueError(f"Unsupported format: {export_job.format}")
            
            # Save file
            file_path = f"/tmp/exports/{export_job_id}.{file_ext}"
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            if isinstance(content, bytes):
                with open(file_path, 'wb') as f:
                    f.write(content)
            else:
                with open(file_path, 'w') as f:
                    f.write(content)
            
            export_job.file_path = file_path
            export_job.file_size = os.path.getsize(file_path)
            export_job.status = 'completed'
            export_job.completed_at = datetime.utcnow()
            export_job.expires_at = datetime.utcnow() + timedelta(days=7)
        
        except Exception as e:
            export_job.status = 'failed'
            export_job.error_message = str(e)
        
        finally:
            db.commit()
    
    @staticmethod
    def create_scheduled_export(
        db: Session,
        user_id: str,
        export_type: str,
        format: str,
        schedule: str,
        email_recipients: List[str],
        filters: Dict = None
    ) -> ScheduledExport:
        """Create a scheduled export"""
        scheduled_export = ScheduledExport(
            user_id=user_id,
            export_type=export_type,
            format=format,
            schedule=schedule,
            email_recipients=email_recipients,
            filters=filters or {}
        )
        db.add(scheduled_export)
        db.commit()
        return scheduled_export
```

#### Step 3: Export Endpoints

**File:** `archiveorigin_backend_api/routes/exports.py`

```python
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from services.export_service import ExportService
from database import get_db
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/exports", tags=["exports"])

class ExportJobCreate(BaseModel):
    export_type: str
    format: str
    filters: Optional[dict] = None

@router.post("/jobs")
async def create_export_job(
    export_job: ExportJobCreate,
    user_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create an export job"""
    try:
        job = ExportService.create_export_job(
            db,
            user_id,
            export_job.export_type,
            export_job.format,
            export_job.filters
        )
        
        # Add background task
        # background_tasks.add_task(
        #     ExportService.process_export_job,
        #     db,
        #     job.id,
        #     data_fetcher
        # )
        
        return {
            'export_job_id': job.id,
            'status': job.status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/{export_job_id}")
async def get_export_job_status(
    export_job_id: str,
    db: Session = Depends(get_db)
):
    """Get export job status"""
    try:
        job = ExportService.get_export_job(db, export_job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Export job not found")
        
        return {
            'export_job_id': job.id,
            'status': job.status,
            'row_count': job.row_count,
            'file_size': job.file_size,
            'created_at': job.created_at.isoformat(),
            'completed_at': job.completed_at.isoformat() if job.completed_at else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/{export_job_id}/download")
async def download_export(
    export_job_id: str,
    db: Session = Depends(get_db)
):
    """Download export file"""
    try:
        job = ExportService.get_export_job(db, export_job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Export job not found")
        
        if job.status != 'completed':
            raise HTTPException(status_code=400, detail="Export not ready")
        
        return FileResponse(
            job.file_path,
            filename=f"export_{export_job_id}.{job.format}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Success Criteria

- ✅ Export data models created
- ✅ Export service implemented
- ✅ CSV export working
- ✅ JSON export working
- ✅ Excel export working
- ✅ PDF export working
- ✅ Export endpoints available
- ✅ Scheduled exports configured
- ✅ File management working
- ✅ Tests passing

---

## Files to Create/Modify

1. **NEW:** `archiveorigin_backend_api/models/exports.py` - Export models
2. **NEW:** `archiveorigin_backend_api/services/export_service.py` - Export service
3. **NEW:** `archiveorigin_backend_api/routes/exports.py` - Export endpoints

---

## Dependencies

- `openpyxl` - Excel export
- `reportlab` - PDF export
- `sqlalchemy` - ORM

---

## Resources

- [Python CSV Module](https://docs.python.org/3/library/csv.html)
- [openpyxl Documentation](https://openpyxl.readthedocs.io/)
- [ReportLab Documentation](https://www.reportlab.com/docs/reportlab-userguide.pdf)

---

**Created:** November 12, 2025  
**For:** Augment Agent  
**Status:** Ready for Implementation
