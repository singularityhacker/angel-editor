from dataclasses import dataclass
from typing import Protocol


@dataclass
class FrameScore:
    t: float
    category: str
    score: float
    labels: list[str]


class VisualDetector(Protocol):
    model_id: str

    def detect(self, frames) -> list[FrameScore]: ...


class NudityDetector:
    model_id = "nudenet:default"

    def __init__(self):
        from nudenet import NudeDetector

        self.model = NudeDetector()

    def detect(self, frames):
        result = []
        for t, frame in frames:
            hits = [h for h in self.model.detect(frame) if h["class"].endswith("_EXPOSED")]
            result.append(
                FrameScore(
                    t,
                    "nudity",
                    max((h["score"] for h in hits), default=0),
                    [h["class"] for h in hits],
                )
            )
        return result


class ViolenceDetector:
    def __init__(self, model_id="ViT-B-32", pretrained="laion2b_s34b_b79k"):
        import open_clip
        import torch

        self.torch = torch
        self.model_id = f"open_clip:{model_id}:{pretrained}:prompts-v1"
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_id, pretrained=pretrained
        )
        self.model.eval()
        self.prompts = ["a peaceful scene", "physical violence", "graphic gore", "visible blood"]
        with torch.no_grad():
            self.text = self.model.encode_text(open_clip.get_tokenizer(model_id)(self.prompts))
            self.text /= self.text.norm(dim=-1, keepdim=True)

    def detect(self, frames):
        from PIL import Image

        result = []
        with self.torch.no_grad():
            for t, frame in frames:
                features = self.model.encode_image(
                    self.preprocess(Image.fromarray(frame[:, :, ::-1])).unsqueeze(0)
                )
                features /= features.norm(dim=-1, keepdim=True)
                probabilities = (100 * features @ self.text.T).softmax(dim=-1)[0]
                score, index = probabilities[1:].max(dim=0)
                result.append(
                    FrameScore(t, "violence", float(score), [self.prompts[int(index) + 1]])
                )
        return result
