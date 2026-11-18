from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.backend_table import BackendDefaults, BackendTable
from schemas.backend_table_schema import BackendTableUpdate


class BackendTableService:

    NULLABLE_FIELDS = {
        "bank_strikes",
        "nifty_strikes",
        "fin_strikes",
    }

    @staticmethod
    def get_or_create(db: Session, user_id: str):

        record = (
            db.query(BackendTable)
            .filter(BackendTable.user_id == user_id)
            .first()
        )

        if record:
            return record

        record = BackendTable(
            user_id=user_id,
            **BackendDefaults.DEFAULT_CONFIG,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def serialize(record):

        return {
            field: getattr(record, field)
            for field in BackendDefaults.DEFAULT_CONFIG
        }

    @classmethod
    def get_config(cls, db: Session, user_id: str):

        record = cls.get_or_create(db, user_id)

        return {
            "success": True,
            "user_id": record.user_id,
            "data": cls.serialize(record),
        }

    @classmethod
    def update_config(
        cls,
        db: Session,
        user_id: str,
        updates: BackendTableUpdate,
    ):

        values = updates.model_dump(exclude_unset=True)

        if not values:
            raise HTTPException(
                status_code=422,
                detail="Provide at least one backend setting to update.",
            )

        invalid_nulls = [
            field
            for field, value in values.items()
            if value is None and field not in cls.NULLABLE_FIELDS
        ]
        if invalid_nulls:
            raise HTTPException(
                status_code=422,
                detail=(
                    "These backend settings cannot be null: "
                    + ", ".join(invalid_nulls)
                ),
            )

        record = cls.get_or_create(db, user_id)

        for field, value in values.items():
            setattr(record, field, value)

        db.commit()
        db.refresh(record)

        return {
            "success": True,
            "message": "Backend settings updated.",
            "user_id": record.user_id,
            "data": cls.serialize(record),
        }
