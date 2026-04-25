from functools import lru_cache
from io import BytesIO

from PIL import Image

from .model_registry import get_model_spec
from .notebook_artifacts import ClipNotebookEmbedder, DinoNotebookEmbedder


class BaseImageEmbedder:
    def __init__(self, model_id: str | None = None):
        spec = get_model_spec(model_id)
        self.model_id = spec.model_id
        self.family = spec.family
        self.source = spec.source
        self.checkpoint_path = spec.checkpoint_path
        self.vector_size = spec.vector_size
        self.gradcam_supported = spec.gradcam_supported
        self._loaded = False

    def _normalize_vector(self, vector):
        torch = self._torch
        return torch.nn.functional.normalize(vector, p=2, dim=1)

    def _prepare_image(self, image_bytes: bytes):
        return Image.open(BytesIO(image_bytes)).convert("RGB")

    def embed(self, image_bytes: bytes) -> list[float]:
        raise NotImplementedError


class DINOv2Embedder(BaseImageEmbedder):
    def _load(self) -> None:
        if self._loaded:
            return

        import torch

        self._torch = torch
        self.model = DinoNotebookEmbedder(self.source, self.checkpoint_path)
        self.processor = self.model.processor
        self.model.eval()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self._loaded = True

    def embed(self, image_bytes: bytes) -> list[float]:
        self._load()

        torch = self._torch
        image = self._prepare_image(image_bytes)
        with torch.inference_mode():
            vector = self.model.encode_pil_images([image]).to(self.device)
        return vector[0].cpu().tolist()


class CLIPImageEmbedder(BaseImageEmbedder):
    def _load(self) -> None:
        if self._loaded:
            return

        import torch

        self._torch = torch
        self.model = ClipNotebookEmbedder(self.source, self.checkpoint_path)
        self.processor = self.model.processor
        self.model.eval()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self._loaded = True

    def embed(self, image_bytes: bytes) -> list[float]:
        self._load()

        torch = self._torch
        image = self._prepare_image(image_bytes)
        with torch.inference_mode():
            vector = self.model.encode_pil_images([image]).to(self.device)
        return vector[0].cpu().tolist()


@lru_cache(maxsize=None)
def get_embedder(model_id: str | None = None) -> BaseImageEmbedder:
    spec = get_model_spec(model_id)
    if spec.family == "dinov2":
        return DINOv2Embedder(spec.model_id)
    if spec.family == "clip":
        return CLIPImageEmbedder(spec.model_id)
    raise ValueError(f"unsupported model family: {spec.family}")
