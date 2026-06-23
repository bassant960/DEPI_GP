import os
import uuid
import httpx
import shutil
from pathlib import Path
from fastapi import UploadFile

# ============================================================
# Model Configuration
# ============================================================

MODEL_API_URL = os.getenv("MODEL_API_URL", "https://api-inference.huggingface.co/models/your-tryon-model")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "")   # Set your HuggingFace or model API key in .env

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ============================================================
# Model Wrapper Class
# ============================================================

class ModelWrapper:
    """
    Wraps the virtual try-on AI model.
    Handles image preparation, API call, and result saving.
    """

    def __init__(self):
        self.model_url  = MODEL_API_URL
        self.api_key    = MODEL_API_KEY
        self.model_name = "OOTD-Diffusion v2.1"
        self.is_ready   = True

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

    def _save_result(self, image_bytes: bytes) -> str:
        """Saves model output bytes to disk and returns the public URL path."""
        filename = f"result_{uuid.uuid4().hex}.jpg"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        return f"/uploads/{filename}"

    async def run(self, person_image: UploadFile, outfit_url: str) -> dict:
        """
        Main inference method.
        Sends person image + outfit URL to the AI model API.
        Returns the result image URL.

        Args:
            person_image : uploaded photo of the user
            outfit_url   : URL of the outfit to try on

        Returns:
            dict with result_url key
        """
        if not self.is_ready:
            raise RuntimeError("Model is not ready. Please try again later.")

        # Save the person image locally
        person_path = self._save_upload(person_image)

        try:
            # ── Call the AI model API ──
            async with httpx.AsyncClient(timeout=60.0) as client:
                with open(person_path, "rb") as img_file:
                    response = await client.post(
                        self.model_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}"
                        },
                        data={
                            "outfit_url": outfit_url
                        },
                        files={
                            "person_image": img_file
                        }
                    )

            if response.status_code != 200:
                raise RuntimeError(f"Model API error: {response.status_code} – {response.text}")

            # Save and return the result image
            result_url = self._save_result(response.content)
            return {"result_url": result_url}

        finally:
            # Clean up the temporary person image
            if os.path.exists(person_path):
                os.remove(person_path)


# ============================================================
# Singleton instance — import this in main.py
# ============================================================

model = ModelWrapper()