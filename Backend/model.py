import os
import uuid
import httpx
import base64
import aiofiles
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# Config
# ============================================================

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ============================================================
# ModelWrapper — يتكلم مع Colab/Kaggle عبر ngrok tunnel
# ============================================================

class ModelWrapper:
    """
    بيبعت صورة الشخص + اللبس للـ Colab server عبر ngrok
    ويستقبل النتيجة كـ base64 أو raw image bytes
    """

    def __init__(self):
        # URL الـ ngrok اللي بتجيبه من Colab كل مرة تشغله
        # مثال: https://xxxx-xx-xx.ngrok-free.app
        base_url = os.getenv("MODEL_API_URL", "https://steadfast-uncheck-appraiser.ngrok-free.dev").rstrip("/")

        # لو اللينك المحفوظ فيه /api/vwear/tryon من الكولاود القديم، بنقطعه
        # ونوحد الـ endpoint على /tryon
        if "/api/vwear/tryon" in base_url:
            base_url = base_url.replace("/api/vwear/tryon", "")

        self.base_url  = base_url
        self.tryon_url = f"{base_url}/tryon"
        self.health_url = f"{base_url}/health"
        self.model_name = "CatVTON via Colab"

    def status(self) -> dict:
        return {
            "model":    self.model_name,
            "base_url": self.base_url,
            "tryon_endpoint": self.tryon_url,
        }

    # ── قراءة ملف (لوكال path) أو URL ────────────────────

    async def _read_file(self, path_or_url: str) -> tuple[str, bytes, str]:
     if path_or_url.startswith("http"):
        # URL خارجي — نحمله
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(path_or_url)
            r.raise_for_status()
            return ("outfit.jpg", r.content, "image/jpeg")
     else:
        # Local file path — نقرأه من الديسك مباشرة
        async with aiofiles.open(path_or_url, "rb") as f:
            data = await f.read()
        ext = os.path.splitext(path_or_url)[1].lower()
        ct  = "image/png" if ext == ".png" else "image/jpeg"
        return (os.path.basename(path_or_url), data, ct)
    # ── الدالة الرئيسية ───────────────────────────────────

    # تعديل السطر ده عشان يستقبل cloth_type
    async def run(self, person_image_path: str, outfit_url: str, cloth_type: str = "upper") -> dict:
        """
        يبعت الصورتين للـ Colab ويحفظ النتيجة لوكال.
        يرجع {"result_url": "/uploads/result_xxx.jpg"}
        """
        print(f"🚀 Sending to Colab → {self.tryon_url}")

        try:
            person_data = await self._read_file(person_image_path)
            cloth_data  = await self._read_file(outfit_url)
            
            files = {
                "person_image": person_data,   
                "cloth_image":  cloth_data,
            }
            
            # 🔥 السطر الجديد: إضافة الـ cloth_type للبيانات المرسلة
            data_payload = {
                "cloth_type": cloth_type
            }

            async with httpx.AsyncClient(timeout=180.0) as client:
                # 🔥 تعديل الـ post عشان يبعت الـ data
                resp = await client.post(self.tryon_url, files=files, data=data_payload)

            if resp.status_code != 200:
                raise RuntimeError(
                    f"Colab returned {resp.status_code}: {resp.text[:300]}"
                )

            # ── استقبال النتيجة ──────────────────────────
            # الـ Colab server بيرجع JSON فيه result_image كـ base64 data URI
            # مثال: {"success": true, "result_image": "data:image/png;base64,..."}

            content_type = resp.headers.get("content-type", "")

            if "application/json" in content_type:
                # ─── JSON response (base64) ───────────────
                data = resp.json()

                result_b64 = data.get("result_image", "")
                if not result_b64:
                    raise RuntimeError("Colab JSON response missing 'result_image' field")

                # استخرج الـ bytes من الـ data URI
                if "base64," in result_b64:
                    result_b64 = result_b64.split("base64,")[1]

                image_bytes = base64.b64decode(result_b64)

            else:
                # ─── Raw image bytes ─────────────────────
                image_bytes = resp.content

            # ── حفظ الصورة ──────────────────────────────
            filename   = f"result_{uuid.uuid4().hex}.jpg"
            final_path = os.path.join(UPLOAD_DIR, filename)

            with open(final_path, "wb") as f:
                f.write(image_bytes)

            result_url = f"/uploads/{filename}"
            print(f"✅ Result saved → {result_url}")
            return {"result_url": result_url}

        except httpx.TimeoutException:
            raise RuntimeError(
                "Colab server timeout (180s). تأكد إن الـ Colab شغال وفيه GPU."
            )
        except httpx.ConnectError:
            raise RuntimeError(
                f"Can't connect to Colab: {self.base_url}\n"
                "تأكد إن الـ ngrok tunnel شغال وحدّث MODEL_API_URL في .env"
            )
        except Exception as e:
            print(f"❌ AI error: {e}")
            raise RuntimeError(f"AI Processing failed: {e}")

        finally:
            # تنظيف الـ temp person image
            if os.path.exists(person_image_path):
                try:
                    os.remove(person_image_path)
                except Exception:
                    pass


# ── Singleton ──────────────────────────────────────────────
model = ModelWrapper()