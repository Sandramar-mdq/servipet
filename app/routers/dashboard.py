from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.usuario import Usuario
from app.schemas.dashboard import DashboardMetricas, DashboardResumen
from app.services.dashboard import metricas, resumen_dia

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _admin(user: Usuario = Depends(require_roles("ADMIN"))):
    return user


@router.get("/resumen", response_model=DashboardResumen)
def resumen(
    fecha: str | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    from datetime import date as _date

    f = None
    if fecha:
        try:
            f = _date.fromisoformat(fecha)
        except ValueError:
            pass
    return resumen_dia(db, user.comercio_id, f)


@router.get("/metricas", response_model=DashboardMetricas)
def metricas_endpoint(
    dias: int = 30,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    return metricas(db, user.comercio_id, dias)
