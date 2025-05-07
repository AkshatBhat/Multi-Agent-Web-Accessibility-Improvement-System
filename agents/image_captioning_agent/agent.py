import json, os
from pathlib import Path
from typing import List, Dict, Optional

import torch
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration


class ImageCaptioningAgent:
    """
    Crops bounding boxes defined in a Web-UI JSON and produces captions
    with a BLIP model.  Structure mirrors 'SemanticAgent'.
    """

    def __init__(
        self,
        device: Optional[str] = None,
        *,
        model_id: str = "Salesforce/blip-image-captioning-base",
        batch_size: int = 8,
        root: str | os.PathLike | None = None,
        hf_token: Optional[str] = None,
    ) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.batch_size = batch_size
        self.root = Path(root) if root else None

        self.processor = BlipProcessor.from_pretrained(model_id, token=hf_token)
        self.model = (
            BlipForConditionalGeneration.from_pretrained(model_id, token=hf_token)
            .to(self.device)
            .eval()
        )

    # ------------------------------------------------------------ helpers
    def _abs_path(self, path: str) -> str:
        p = Path(path)
        if p.is_absolute() or self.root is None:
            return str(p)
        return str(self.root / p)

    # ------------------------------------------------------------ stage 1
    def preprocess(self, raw_json: str) -> List[Dict]:
        doc = json.loads(raw_json)
        crops: list[dict] = []
        for vp in doc.get("viewports", []):
            sc_path = vp.get("screenshot")
            if not sc_path:
                continue
            full_path = self._abs_path(sc_path)
            try:
                screenshot = Image.open(full_path).convert("RGB")
            except FileNotFoundError as exc:
                raise FileNotFoundError(f"Screenshot not found: {full_path}") from exc

            for obj in vp.get("image_captioning", []):
                bbox = obj.get("bbox", {})
                x, y = bbox.get("x", 0), bbox.get("y", 0)
                w, h = bbox.get("width", 0), bbox.get("height", 0)
                if w <= 0 or h <= 0:
                    continue
                crop = screenshot.crop((x, y, x + w, y + h))
                crops.append(
                    {
                        "nodeId": obj.get("nodeId"),
                        "alt": obj.get("alt", ""),
                        "image": crop,
                    }
                )
        if not crops:
            raise ValueError("No valid bounding boxes found in the JSON input.")
        return crops

    # ------------------------------------------------------------ stage 2
    @torch.inference_mode()
    def generate_summary(
        self, crops: List[Dict], *, max_tokens: int = 25
    ) -> List[tuple[str, str, str]]:
        out: list[tuple[str, str, str]] = []
        bs = self.batch_size
        for i in range(0, len(crops), bs):
            batch = crops[i : i + bs]
            imgs = [item["image"] for item in batch]

            with torch.autocast(
                device_type=self.device,
                dtype=torch.float16,
                enabled=self.device == "cuda",
            ):
                enc = self.processor(
                    images=imgs, return_tensors="pt", padding=True
                ).to(self.device)
                ids = self.model.generate(**enc, max_new_tokens=max_tokens)
                caps = self.processor.batch_decode(ids, skip_special_tokens=True)

            for itm, cap in zip(batch, caps):
                out.append((itm["nodeId"], itm["alt"], cap.strip()))
        return out

    # ------------------------------------------------------------ public
    def handle(self, raw_json: str) -> str:
        triples = self.generate_summary(self.preprocess(raw_json))
        sents = []
        for node_id, alt, cap in triples:
            if alt:  # alt text present
                sents.append(
                    f"For nodeId {node_id}, the alt image text is '{alt}', and the generated caption is '{cap}'."
                )
            else:    # no alt text
                sents.append(
                    f"For nodeId {node_id}, the alt text is missing and the generated caption is '{cap}'."
                )
        return " ".join(sents)