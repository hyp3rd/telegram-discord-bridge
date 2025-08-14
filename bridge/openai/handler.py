"""This module handles the communication with the OpenAI API."""

import asyncio
import functools

from openai import OpenAI

from bridge.config import Config
from bridge.logger import Logger
from core import SingletonMeta

config = Config.get_instance()
logger = Logger.get_logger(config.application.name)


class OpenAIHandler(metaclass=SingletonMeta):
    """OpenAI handler class."""

    def __init__(self) -> None:
        self.client = OpenAI(
            api_key=config.openai.api_key,
            organization=config.openai.organization,
        )
        self.model = config.openai.model

    async def analyze_message_and_generate_suggestions(self, text: str) -> str:
        """Analyze the message text and seek for suggestions."""

        loop = asyncio.get_event_loop()
        try:
            create_completion = functools.partial(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Given the message: '{text}', suggest related actions and correlated articles with links:\n"
                            "Related Actions:\n- ACTION1\n- ACTION2\n- ACTION3\n"
                            "Correlated Articles:\n1. ARTICLE1_TITLE - ARTICLE1_LINK\n"
                            "2. ARTICLE2_TITLE - ARTICLE2_LINK\n"
                            "3. ARTICLE3_TITLE - ARTICLE3_LINK\n"
                        ),
                    }
                ],
                temperature=0,
                max_tokens=60,
            )

            response = await loop.run_in_executor(None, create_completion)

            content = response.choices[0].message.content
            suggestion = content.strip() if content else ""

            return suggestion
        except Exception as ex:  # pylint: disable=broad-except
            logger.error("Error generating suggestion: %s", {ex})
            return "Error generating suggestion."

    async def analyze_message_sentiment(self, text: str) -> str:
        """Analyze the message text and seek for suggestions."""

        loop = asyncio.get_event_loop()
        try:
            prompt = None
            for prompt_line in config.openai.sentiment_analysis_prompt:
                prompt = f"{prompt} {prompt_line}\n"

            if prompt is not None:
                prompt = prompt.replace("#text_to_parse", text)

            logger.debug("openai_sentiment_analysis_prompt %s", prompt)

            create_completion = functools.partial(
                self.client.chat.completions.create,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=250,
            )

            response = await loop.run_in_executor(None, create_completion)

            content = response.choices[0].message.content
            suggestion = content.strip() if content else ""

            return suggestion
        except Exception as ex:  # pylint: disable=broad-except
            logger.error("Error generating suggestion: %s", {ex})
            return "Error generating suggestion."

    async def is_spam(self, text: str) -> bool:
        """Classify whether the provided text is spam."""

        loop = asyncio.get_event_loop()
        try:
            create_completion = functools.partial(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Classify the following message as spam or not spam. "
                            "Reply with 'spam' or 'not spam' only.\n"
                            f"Message: {text}"
                        ),
                    }
                ],
                temperature=0,
                max_tokens=10,
            )

            response = await loop.run_in_executor(None, create_completion)

            content = response.choices[0].message.content or ""
            return "spam" in content.lower()
        except Exception as ex:  # pylint: disable=broad-except
            logger.error("Error classifying spam: %s", {ex})
            return False
