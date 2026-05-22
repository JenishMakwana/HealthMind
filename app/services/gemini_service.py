import google.generativeai as genai
from app.core.config import get_settings
from loguru import logger

settings = get_settings()

class GeminiService:
    def __init__(self):
        if not settings.google_api_key:
            logger.warning("GOOGLE_API_KEY not found in settings")
        
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)

    async def generate_response(self, prompt: str, system_instruction: str = None) -> str:
        """
        Generates a response from Gemini based on the provided prompt.
        """
        try:
            # Re-initialize model if system_instruction is provided
            model = self.model
            if system_instruction:
                model = genai.GenerativeModel(
                    settings.gemini_model,
                    system_instruction=system_instruction
                )
            
            response = await model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            return f"Error: {e}"

# Global instance
gemini_service = None

def get_gemini_service():
    global gemini_service
    if gemini_service is None:
        gemini_service = GeminiService()
    return gemini_service
