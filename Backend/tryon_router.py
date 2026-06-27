"""
vwear - CatVTON Bridge Endpoint
================================
أضف الـ router ده لـ FastAPI backend بتاعك.
ببساطة بيبعت الـ request لـ Colab/Kaggle tunnel.
"""

import os
import io
import httpx
import asyncio
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse

# ─────────────────────────────────────────────
# Config - اتحط في .env أو settings بتاعتك
# ─────────────────────────────────────────────
COLAB_TUNNEL_URL = os.getenv(
    "MODEL_API_URL",
    "https://steadfast-uncheck-appraiser.ngrok-free.dev"   # <-- هيتغير كل ما تشغل Colab
)
REQUEST_TIMEOUT  = 120   # seconds - الموديل بياخد وقت

router = APIRouter(prefix="/api/tryon", tags=["Virtual Try-On"])


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────
async def _forward_to_colab(
    person_bytes: bytes,
    cloth_bytes:  bytes,
    person_fname: str,
    cloth_fname:  str,
    cloth_type:   str,
    steps:        int,
    guidance:     float,
    seed:         int,
) -> dict:
    """بيبعت الـ images لـ Colab server ويرجع النتيجة."""

    url = f"{COLAB_TUNNEL_URL.rstrip('/')}/tryon"

    files = {
        "person_image": (person_fname, person_bytes, "image/jpeg"),
        "cloth_image":  (cloth_fname,  cloth_bytes,  "image/jpeg"),
    }
    data = {
        "cloth_type":           cloth_type,
        "num_inference_steps":  str(steps),
        "guidance_scale":       str(guidance),
        "seed":                 str(seed),
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        resp = await client.post(url, files=files, data=data)

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"CatVTON server error: {resp.text[:300]}"
        )

    return resp.json()


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────
@router.get("/health")
async def tryon_health():
    """بيتحقق إن Colab server شغال."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{COLAB_TUNNEL_URL}/health")
        return {
            "backend":     "ok",
            "colab_model": r.json(),
            "tunnel_url":  COLAB_TUNNEL_URL,
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"backend": "ok", "colab_model": "unreachable", "error": str(e)},
        )


@router.post("/")
async def virtual_tryon(
    person_image: UploadFile = File(..., description="صورة الشخص"),
    cloth_image:  UploadFile = File(..., description="صورة الملبس"),
    cloth_type:   str        = Form("upper",  description="upper | lower | overall"),
    steps:        int        = Form(50,        description="عدد خطوات الـ inference"),
    guidance:     float      = Form(2.5,       description="Guidance scale"),
    seed:         int        = Form(42,        description="Random seed للـ reproducibility"),
):
    """
    الـ endpoint الرئيسي للـ virtual try-on.

    - **person_image**: صورة الشخص (JPG/PNG)
    - **cloth_image**: صورة الملبس على خلفية بيضاء
    - **cloth_type**: نوع الملبس (upper/lower/overall)
    """

    # Validate file types
    allowed = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
    for f, name in [(person_image, "person_image"), (cloth_image, "cloth_image")]:
        ct = f.content_type or ""
        if ct not in allowed and not f.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            raise HTTPException(400, f"{name}: يجب أن يكون صورة (JPG/PNG/WEBP)")

    # Validate cloth_type
    if cloth_type not in {"upper", "lower", "overall"}:
        raise HTTPException(400, "cloth_type يجب أن يكون: upper | lower | overall")

    # Read files
    person_bytes = await person_image.read()
    cloth_bytes  = await cloth_image.read()

    # Size limits (10 MB each)
    for data, name in [(person_bytes, "person_image"), (cloth_bytes, "cloth_image")]:
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(413, f"{name} أكبر من 10MB")

    # Forward to Colab
    try:
        result = await _forward_to_colab(
            person_bytes=person_bytes,
            cloth_bytes=cloth_bytes,
            person_fname=person_image.filename or "person.jpg",
            cloth_fname=cloth_image.filename or "cloth.jpg",
            cloth_type=cloth_type,
            steps=steps,
            guidance=guidance,
            seed=seed,
        )
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(504, "الموديل استغرق وقت طويل - جرب تقلل الـ steps")
    except httpx.ConnectError:
        raise HTTPException(503, "مش قادر يوصل لـ Colab server - تأكد إن الـ tunnel شغال")
    except Exception as e:
        raise HTTPException(500, f"خطأ غير متوقع: {str(e)}")

    return JSONResponse({
        "success":      True,
        "result_image": result.get("result_image"),   # base64 data URI
        "cloth_type":   cloth_type,
        "seed":         seed,
    })


# ─────────────────────────────────────────────
# How to register in your main.py
# ─────────────────────────────────────────────
#
#   from tryon_router import router as tryon_router
#   app.include_router(tryon_router)
#
# ─────────────────────────────────────────────
