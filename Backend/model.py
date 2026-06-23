from io import BytesIO
import os
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile
from gradio_client import Client, handle_file
from PIL import Image
from dotenv import load_dotenv
import requests

load_dotenv()

# ============================================================
# Model Configuration
# ============================================================

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ============================================================
# Model Wrapper Class
# ============================================================

class ModelWrapper:
    """
    Wraps the virtual try-on AI model.
    """

    def __init__(self):
        self.api_key = os.getenv("MODEL_API_KEY") or None
        self.model_url = os.getenv("MODEL_API_URL", "zhengchong/CatVTON")
        self.model_name = "CatVTON via Gradio"
        
        # محاولة الاتصال
        self.is_ready = False
        try:
            if self.api_key:
                test_client = Client(self.model_url, token=self.api_key)
            else:
                test_client = Client(self.model_url)
            self.is_ready = True
            print(f"✅ Connected to {self.model_url}")
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            self.is_ready = False

    def status(self) -> dict:
        return {
            "model": self.model_name,
            "ready": self.is_ready,
            "api_url": self.model_url,
            "has_token": bool(self.api_key),
        }

    def _save_result_image(self, image_path: str) -> str:
        """Save result image, converting RGBA to RGB if needed."""
        try:
            print(f"📸 Opening result image: {image_path}")
            
            # تحميل الصورة إذا كانت URL
            if image_path.startswith('http'):
                response = requests.get(image_path)
                img = Image.open(BytesIO(response.content))
            else:
                img = Image.open(image_path)
            
            print(f"📸 Image mode: {img.mode}, size: {img.size}")
            
            # ⭐ تحويل RGBA لـ RGB مع خلفية بيضاء
            if img.mode == 'RGBA':
                print("🔄 Converting RGBA to RGB with white background")
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            elif img.mode != 'RGB':
                print(f"🔄 Converting {img.mode} to RGB")
                img = img.convert('RGB')
            
            # حفظ كـ JPEG
            filename = f"result_{uuid.uuid4().hex}.jpg"
            final_path = os.path.join(UPLOAD_DIR, filename)
            img.save(final_path, 'JPEG', quality=95)
            print(f"💾 Saved to: {final_path}")
            
            return f"/uploads/{filename}"
            
        except Exception as e:
            print(f"❌ Error saving image: {e}")
            raise

    async def run(self, person_image_path: str, outfit_url: str) -> dict:
        """Main inference method."""
        if not self.is_ready:
            raise RuntimeError("Model is not ready. Please check your connection.")

        try:
            print("🚀 Starting AI inference...")
            
            # تسطيح الصور قبل الإرسال
            self._flatten_image(person_image_path)
            
            if outfit_url and os.path.exists(outfit_url) and not outfit_url.startswith("http"):
                self._flatten_image(outfit_url)

            # ⭐⭐⭐ الاتصال بالموديل بالطريقة الصحيحة من الـ API docs
            print(f"🔗 Connecting to model: {self.model_url}")
            if self.api_key:
                client = Client(self.model_url, token=self.api_key)
            else:
                client = Client(self.model_url)
            
            # تجهيز البيانات بالشكل المطلوب
            person_img_dict = {
                "background": handle_file(person_image_path),
                "layers": [],
                "composite": None
            }

            print("📤 Sending request to AI model...")
            print(f"📤 Person image: {person_image_path}")
            print(f"📤 Outfit: {outfit_url}")
            
            # ⭐⭐⭐ الحل: استخدام show_type="result only" عشان ناخد الصورة النهائية فقط
            result = client.predict(
                person_image=person_img_dict,
                cloth_image=handle_file(outfit_url),
                cloth_type="upper",
                num_inference_steps=50,
                guidance_scale=2.5,
                seed=42,
                show_type="result only",  # ⭐ التغيير المهم
                api_name="/submit_function"
            )

            print(f"📥 Result type: {type(result)}")
            print(f"📥 Result: {result}")

            # ⭐ استخراج مسار الصورة من النتيجة
            result_path = None
            
            if isinstance(result, dict):
                # النتيجة dict فيها path أو url
                result_path = result.get('path') or result.get('url')
                print(f"📥 Extracted path from dict: {result_path}")
            elif isinstance(result, str):
                result_path = result
                print(f"📥 Result is string: {result_path}")
            elif isinstance(result, (list, tuple)) and len(result) > 0:
                # لو النتيجة list
                last_item = result[-1]
                if isinstance(last_item, dict):
                    result_path = last_item.get('path') or last_item.get('url')
                elif isinstance(last_item, str):
                    result_path = last_item
                print(f"📥 Extracted from list: {result_path}")

            if not result_path:
                raise RuntimeError(f"Could not extract image path from result: {result}")

            # ⭐ حفظ الصورة الناتجة
            result_url = self._save_result_image(result_path)
            print(f"✅ Final result URL: {result_url}")
            
            return {"result_url": result_url}

        except Exception as e:
            print(f"❌ AI Processing failed: {str(e)}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Gradio AI Processing failed: {str(e)}")

        finally:
            # تنظيف الملفات المؤقتة
            if os.path.exists(person_image_path):
                try:
                    os.remove(person_image_path)
                    print(f"🗑️ Cleaned up: {person_image_path}")
                except:
                    pass

    def _flatten_image(self, image_path: str):
        """تسطيح الصورة وإزالة الشفافية"""
        if not image_path or not os.path.exists(image_path) or image_path.startswith("http"):
            return
        
        try:
            print(f"🔄 Flattening image: {image_path}")
            with Image.open(image_path) as img:
                original_mode = img.mode
                if img.mode in ('RGBA', 'LA', 'P'):
                    if img.mode == 'RGBA':
                        background = Image.new("RGB", img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[-1])
                        img = background
                    else:
                        img = img.convert('RGB')
                    
                    img.save(image_path, "JPEG", quality=95)
                    print(f"✅ Flattened {image_path} from {original_mode} to RGB")
        except Exception as e:
            print(f"⚠️ Could not flatten {image_path}: {e}")

# ============================================================
# Singleton
# ============================================================

model = ModelWrapper()