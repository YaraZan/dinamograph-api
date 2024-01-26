from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional

from fastapi import UploadFile, File, HTTPException, status

from ai.core.dinamograph import create_model, predict
from ai.helpers.data_helper import DataHelper
from database.database import MainSession
from database.models import Marker
from database.models.ai_marker import AIMarker
from database.models.ai_model import AIModel
from service.meta.ai_service_meta import AIServiceMeta

# Main app database instance
main_database = MainSession()

# DataHelper instance
data_helper = DataHelper()


class AIService(AIServiceMeta):
    def create_model(self, model_name: str):
        existing_model = main_database.query(AIModel).filter(AIModel.name == model_name).first()

        if existing_model is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Модель с таким названием уже существует")

        ai_markers = create_model(model_name=model_name)

        new_model = AIModel(
            name=model_name,
        )
        main_database.add(new_model)

        for ai_marker in ai_markers:
            matching_marker = main_database.query(Marker).filter(Marker.id == int(ai_marker)).first()

            if matching_marker is None:
                HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный маркер для динамограммы")

            new_ai_marker = AIMarker()
            new_ai_marker.marker_id = matching_marker.id
            new_ai_marker.ai_model_id = new_model.id
            main_database.add(new_ai_marker)

        main_database.commit()

    async def predict(
            self,
            model_name: str,
            is_raw: bool = False,
            image: Optional[UploadFile] = File(None),
            raw: Optional[Dict[Any, Any]] = None
    ) -> str:
        matching_model = main_database.query(AIModel).filter(AIModel.name == model_name).first()

        if matching_model is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Модели с таким названием не существует")

        if is_raw and raw is not None:
            image_bytes = data_helper.create_image_bytes_from_raw(raw['x'], raw['y'])
        else:
            image_bytes = await image.read()

        prediction_index = predict(model_name, image_bytes)

        ai_model_matching_markers = main_database.query(AIMarker).order_by(AIMarker.marker_id).filter(AIMarker.ai_model == matching_model).all()

        if ai_model_matching_markers is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не найдены маркеры для динамограммы")

        prediction_message_raw = ai_model_matching_markers[prediction_index].original_marker.name

        return str(prediction_message_raw)


