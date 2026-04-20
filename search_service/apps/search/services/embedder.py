from io import BytesIO

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModel


MODEL_NAME = "facebook/dinov2-base"


class DINOv2Embedder:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.processor = AutoImageProcessor.from_pretrained(MODEL_NAME)
            cls._instance.model = AutoModel.from_pretrained(MODEL_NAME)
            cls._instance.model.eval()
        return cls._instance

    def embed(self, image_bytes: bytes) -> list[float]:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(**inputs)
            pooled = outputs.last_hidden_state[:, 0, :]
            vector = torch.nn.functional.normalize(pooled, p=2, dim=1)
        return vector[0].cpu().tolist()
