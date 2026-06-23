import os
import uuid
import requests
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv
from gradio_client import Client, handle_file

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
            if image_path.startswith('http'):
                response = requests.get(image_path)
                img = Image.open(BytesIO(response.content))
            else:
                img = Image.open(image_path)
            
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            filename = f"result_{uuid.uuid4().hex}.jpg"
            final_path = os.path.join(UPLOAD_DIR, filename)
            img.save(final_path, 'JPEG', quality=95)
            
            return f"/uploads/{filename}"
            
        except Exception as e:
            print(f"❌ Error saving image: {e}")
            raise

    def _prepare_image_as_png(self, image_path: str) -> str:
        if not image_path or not os.path.exists(image_path) or image_path.startswith("http"):
            return image_path
        
        try:
            print(f"🔄 Converting to PNG: {image_path}")
            with Image.open(image_path) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[-1])
                    else:
                        img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1])
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                new_path = image_path.rsplit('.', 1)[0] + '.png'
                img.save(new_path, "PNG")
                
                if new_path != image_path:
                    os.remove(image_path)
                
                print(f"✅ Saved as PNG: {new_path}")
                return new_path
                
        except Exception as e:
            print(f"⚠️ Error converting to PNG: {e}")
            return image_path

    def _create_blank_mask(self, image_path: str) -> str:
        """⭐ السحر الجديد: إنشاء قناع شفاف بالكامل لإرضاء الموديل وتجنب الـ IndexError"""
        if not image_path or not os.path.exists(image_path) or image_path.startswith("http"):
            return None
            
        try:
            with Image.open(image_path) as img:
                # إنشاء صورة شفافة بالكامل بنفس الحجم
                blank = Image.new('RGBA', img.size, (0, 0, 0, 0))
                blank_path = image_path.rsplit('.', 1)[0] + '_mask.png'
                blank.save(blank_path, "PNG")
                print(f"✅ Created blank mask: {blank_path}")
                return blank_path
        except Exception as e:
            print(f"⚠️ Error creating blank mask: {e}")
            return None

    async def run(self, person_image_path: str, outfit_url: str) -> dict:
        blank_mask_path = None
        if not self.is_ready:
            raise RuntimeError("Model is not ready. Please check your connection.")

        try:
            print("🚀 Starting AI inference...")
            
            person_image_path = self._prepare_image_as_png(person_image_path)
            
            # 👇 إنشاء الماسك الشفاف الوهمي
            blank_mask_path = self._create_blank_mask(person_image_path)
            
            if outfit_url and os.path.exists(outfit_url) and not outfit_url.startswith("http"):
                outfit_url = self._prepare_image_as_png(outfit_url)

            if self.api_key:
                client = Client(self.model_url, token=self.api_key)
            else:
                client = Client(self.model_url)
            
            # ⭐ هنا الخدعة: وضع الماسك الشفاف في layers عشان الموديل ميضربش IndexError
            person_img_dict = {
                "background": handle_file(person_image_path),
                "layers": [handle_file(blank_mask_path)] if blank_mask_path else [],
                "composite": handle_file(person_image_path)
            }

            print("📤 Sending request to AI model...")
            
            result = client.predict(
                person_image=person_img_dict,
                cloth_image=handle_file(outfit_url),
                cloth_type="upper",
                num_inference_steps=50,
                guidance_scale=2.5,
                seed=42,
                show_type="result only",  
                api_name="/submit_function"
            )

            result_path = None
            if isinstance(result, dict):
                result_path = result.get('path') or result.get('url')
            elif isinstance(result, str):
                result_path = result
            elif isinstance(result, (list, tuple)) and len(result) > 0:
                last_item = result[-1]
                if isinstance(last_item, dict):
                    result_path = last_item.get('path') or last_item.get('url')
                elif isinstance(last_item, str):
                    result_path = last_item

            if not result_path:
                raise RuntimeError(f"Could not extract image path from result: {result}")

            result_url = self._save_result_image(result_path)
            print(f"✅ Final result URL: {result_url}")
            
            return {"result_url": result_url}

        except Exception as e:
            print(f"❌ AI Processing failed: {str(e)}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Gradio AI Processing failed: {str(e)}")

        finally:
            # تنظيف الملفات المؤقتة بما فيها الماسك الوهمي
            if os.path.exists(person_image_path):
                try:
                    os.remove(person_image_path)
                except:
                    pass
            if blank_mask_path and os.path.exists(blank_mask_path):
                try:
                    os.remove(blank_mask_path)
                except:
                    pass

# ============================================================
# Singleton
# ============================================================

model = ModelWrapper()