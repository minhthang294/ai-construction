"""Optional vision suggestions for site photos.

Vision output is always a proposal.  The Engineering AI module never marks a
photo as confirmed, never writes GPS/dimensions/quantities and never changes a
SitePhoto record.  The Site Report module must apply a suggestion only after the
engineer explicitly confirms it.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from typing import List, Optional, Protocol

from .constants import VISION_DISCLAIMER


@dataclass
class VisionRegion:
    left: float
    top: float
    width: float
    height: float


@dataclass
class VisionSuggestion:
    suggested_category: Optional[str] = None
    suggested_caption: Optional[str] = None
    regions: List[VisionRegion] = field(default_factory=list)
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)


class VisionProvider(Protocol):
    name: str

    def suggest(self, image_bytes: bytes, mime_type: str) -> VisionSuggestion:
        ...


class NoopVisionProvider:
    """Safe default: no model configured, no fabricated suggestion."""

    name = "none"

    def suggest(self, image_bytes: bytes, mime_type: str) -> VisionSuggestion:
        return VisionSuggestion(
            warnings=[
                "Chưa cấu hình vision provider; cần kỹ sư tự phân loại và đặt caption."
            ]
        )


class OpenAICompatibleVisionProvider:
    name = "openai_compatible_vision"

    def __init__(self, endpoint: str, model: str, api_key: str, timeout: float = 60.0) -> None:
        self.endpoint = endpoint
        self.model = model
        self._api_key = api_key
        self.timeout = timeout
        self.name = f"openai_compatible:{model}"

    def suggest(self, image_bytes: bytes, mime_type: str) -> VisionSuggestion:
        import httpx

        encoded = base64.b64encode(image_bytes).decode("ascii")
        prompt = (
            "Đề xuất loại ảnh công trường và caption mô tả tối giản. Chỉ mô tả "
            "những gì nhìn thấy; không suy đoán kích thước, khối lượng, GPS, "
            "ngày tháng hoặc chất lượng nghiệm thu. Trả JSON: "
            '{"category": string|null, "caption": string|null, '
            '"regions": [{"left":0-1,"top":0-1,"width":0-1,"height":0-1}], '
            '"confidence": 0-1}.'
        )
        response = httpx.post(
            self.endpoint,
            json={
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                            },
                        ],
                    }
                ],
            },
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        import json

        content = response.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        regions = []
        for item in data.get("regions") or []:
            try:
                regions.append(
                    VisionRegion(
                        left=max(0.0, min(1.0, float(item["left"]))),
                        top=max(0.0, min(1.0, float(item["top"]))),
                        width=max(0.0, min(1.0, float(item["width"]))),
                        height=max(0.0, min(1.0, float(item["height"]))),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return VisionSuggestion(
            suggested_category=data.get("category"),
            suggested_caption=data.get("caption"),
            regions=regions,
            confidence=max(0.0, min(1.0, float(data.get("confidence") or 0.0))),
            warnings=[VISION_DISCLAIMER],
        )


def vision_from_env() -> VisionProvider:
    name = (os.getenv("ENGINEERING_AI_VISION_PROVIDER") or "none").strip().lower()
    if name in {"openai", "openai_compatible", "openai-compatible"}:
        endpoint = (os.getenv("ENGINEERING_AI_VISION_URL") or "").strip()
        model = (os.getenv("ENGINEERING_AI_VISION_MODEL") or "").strip()
        api_key = (os.getenv("ENGINEERING_AI_API_KEY") or "").strip()
        if endpoint and model and api_key:
            return OpenAICompatibleVisionProvider(
                endpoint=endpoint,
                model=model,
                api_key=api_key,
                timeout=float(os.getenv("ENGINEERING_AI_TIMEOUT", "60")),
            )
    return NoopVisionProvider()
