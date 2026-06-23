import os
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile
from gradio_client import Client, handle_file
from PIL import Image


# ============================================================
# Model Configuration
# ============================================================

# تأكد أن في ملف الـ .env الـ MODEL_API_URL قيمتها هي: zhengchong/CatVTON
MODEL_API_URL = os.getenv("MODEL_API_URL")
MODEL_API_KEY = os.getenv("MODEL_API_KEY")   # هنا هيكون الـ HuggingFace token بتاعك

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ============================================================
# Model Wrapper Class
# ============================================================

class ModelWrapper:
    """
    Wraps the virtual try-on AI model.
    Handles image preparation, Gradio Space API call, and result saving.
    """

    def __init__(self):
        self.model_url  = MODEL_API_URL
        self.api_key    = MODEL_API_KEY
        self.model_name = "CatVTON via Gradio"
        self.is_ready   = bool(self.model_url)

    def status(self) -> dict:
        """Returns current model status info."""
        return {
            "model":   self.model_name,
            "ready":   self.is_ready,
            "api_url": self.model_url,
        }

    def _save_upload(self, file: UploadFile) -> str:
        """Saves an uploaded file to disk and returns its local path."""
        ext      = Path(file.filename).suffix or ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return filepath

    def _save_result_from_path(self, temp_path: str) -> str:
        """Takes the temporary output path from Gradio, moves it to our uploads directory."""
        if not os.path.exists(temp_path):
            raise FileNotFoundError(f"Result image not found at {temp_path}")
            
        ext = Path(temp_path).suffix or ".png"
        filename = f"result_{uuid.uuid4().hex}{ext}"
        final_path = os.path.join(UPLOAD_DIR, filename)
        
        # نقل الملف من المجلد المؤقت الخاص بـ Gradio إلى مجلد uploads الخاص بمشروعنا
        shutil.move(temp_path, final_path)
        return f"/uploads/{filename}"
    async def run(self, person_image_path: str, outfit_url: str) -> dict:
        """
        Main inference method.
        Sends person image + outfit URL to the Hugging Face Space using Gradio Client.
        Returns the result image URL.
        """
        if not self.is_ready:
            raise RuntimeError("Model is not ready. Please try again later.")

        # دالة داخلية لتسطيح أي صورة وإزالة قنوات الشفافية (RGBA/LA) وتحويلها لـ RGB بيكسل صلب
        # تسطيح الصورة المحلية فقط وإزالة قنوات الشفافية (RGBA)
        def flatten_local_image(image_path):
            # نتأكد أنه مسار ملف محلي وليس رابط URL من الإنترنت
            if image_path and os.path.exists(image_path) and not image_path.startswith("http"):
                try:
                    with Image.open(image_path) as img:
                        if img.mode in ('RGBA', 'LA'):
                            background = Image.new("RGB", img.size, (255, 255, 255))
                            if img.mode == 'RGBA':
                                background.paste(img, mask=img.split()[-1])
                            else:
                                background.paste(img, mask=img.split()[-1])
                            background.save(image_path, "JPEG")
                        elif img.mode != 'RGB':
                            img.convert('RGB').save(image_path, "JPEG")
                except Exception as e:
                    print(f"⚠️ Could not flatten image {image_path}: {e}")

        try:
            # 1. تسطيح صورة الشخص وصورة اللبس قبل إرسالهما للموديل
            flatten_local_image(person_image_path)
            flatten_local_image(outfit_url)

            # 2. الاتصال بـ Hugging Face Space عبر Gradio Client
            client = Client(self.model_url, token=self.api_key)
            
            # 3. تجهيز القاموس بالصيغة الدقيقة لـ CatVTON
            person_img_dict = {
                "background": handle_file(person_image_path),
                "layers": [],
                "composite": None
            }

            # 4. إرسال البيانات بالصيغة المعتمدة لـ CatVTON
            result = client.predict(
                person_image=person_img_dict,
                cloth_image=handle_file(outfit_url),
                cloth_type="upper",
                num_inference_steps=50,
                guidance_scale=2.5,
                seed=42,
                show_type="input & mask & result",
                api_name="/submit_function"
            )

            print("=== GRADIO RAW OUTPUT ===", result)

            # استخراج النتيجة (الصورة الناتجة تكون عادة في العنصر الأخير أو محددة بمسار)
            result_image_path = None
            if isinstance(result, (list, tuple)) and len(result) > 0:
                target_item = result[-1]
                if isinstance(target_item, dict):
                    result_image_path = target_item.get("path") or target_item.get("url")
                elif isinstance(target_item, str):
                    result_image_path = target_item
            
            if not result_image_path:
                result_image_path = result[0] if isinstance(result, (list, tuple)) else result

            if isinstance(result_image_path, dict):
                result_image_path = result_image_path.get("path") or result_image_path.get("url")

            print("=== EXTRACTED IMAGE PATH ===", result_image_path)

            # حفظ النتيجة في مجلد المشروع وإرجاع الـ URL للفرونت اند
            result_url = self._save_result_from_path(result_image_path)
            return {"result_url": result_url}

        except Exception as e:
            raise RuntimeError(f"Gradio AI Processing failed: {str(e)}")

        finally:
            # Clean up the temporary person image
            if os.path.exists(person_image_path):
                os.remove(person_image_path)
# ============================================================
# Singleton instance — import this in main.py
# ============================================================

model = ModelWrapper()