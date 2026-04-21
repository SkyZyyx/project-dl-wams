from functools import lru_cache
from io import BytesIO

from PIL import Image


MODEL_NAME = "facebook/dinov2-base"


class DINOv2Embedder:
    def __init__(self):
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return

        import torch
        from transformers import AutoImageProcessor, AutoModel

        self._torch = torch
        self.processor = AutoImageProcessor.from_pretrained(MODEL_NAME)
        self.model = AutoModel.from_pretrained(MODEL_NAME)
        self.model.eval()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self._loaded = True

    def embed(self, image_bytes: bytes) -> list[float]:
        self._load()

        torch = self._torch
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}

        with torch.inference_mode():
            outputs = self.model(**inputs)
            pooled = outputs.last_hidden_state[:, 0, :]
            vector = torch.nn.functional.normalize(pooled, p=2, dim=1)
        return vector[0].cpu().tolist()


@lru_cache(maxsize=1)
def get_embedder() -> DINOv2Embedder:
    return DINOv2Embedder()
