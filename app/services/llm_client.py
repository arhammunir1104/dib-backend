import asyncio
from openai import AsyncOpenAI, RateLimitError
from app.core.config import settings
from app.logging.setup import logger

class LLMClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        logger.info("Initializing LLM client")
        if not settings.LLM_API_KEY:
            raise ValueError("LLM_API_KEY is not set in environment")
        masked_key = settings.LLM_API_KEY[:4] + "..." + settings.LLM_API_KEY[-4:] if len(settings.LLM_API_KEY) > 8 else "***"
        logger.info(f"Using LLM provider: {settings.LLM_PROVIDER}")
        logger.info(f"Base URL: {settings.LLM_BASE_URL}")
        logger.info(f"API Key (masked): {masked_key}")
        self.client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=120.0,   # increased timeout
        )
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self._initialized = True

    async def generate(self, messages: list[dict], temperature: float = None, max_tokens: int = None) -> str:
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature if temperature is not None else self.temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content
            except RateLimitError as e:
                if attempt == max_retries:
                    raise
                wait_time = 2 ** attempt
                logger.warning(f"Rate limit hit, retrying in {wait_time}s (attempt {attempt}/{max_retries})")
                await asyncio.sleep(wait_time)
            except Exception:
                raise

def get_llm_client() -> LLMClient:
    return LLMClient()