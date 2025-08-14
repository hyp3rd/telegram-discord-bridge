"""This module handles the communication with the OpenAI API."""

import asyncio
import functools
import json
from typing import List, Dict

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

    async def analyze_message_and_generate_suggestions(
        self, text: str
    ) -> List[Dict[str, str]]:
        """Identify factual claims and matching search queries.

        The model is asked to return a JSON array of objects with two keys:

        - ``claim``: the potential factual statement found in the text
        - ``query``: a suggested search query to verify that claim
        """

        loop = asyncio.get_event_loop()
        try:
            create_completion = functools.partial(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "For the following message, list factual claims and a search query "
                            "for each to verify it. Respond with JSON array of objects "
                            "with 'claim' and 'query' fields.\n"
                            f"Message: {text}"
                        ),
                    }
                ],
                temperature=0,
                max_tokens=300,
            )

            response = await loop.run_in_executor(None, create_completion)
            content = response.choices[0].message.content
            if content is None:
                return []
            try:
                return json.loads(content)
            except JSONDecodeError as json_ex:
                logger.error("Failed to parse OpenAI response as JSON: %s. Content: %r", json_ex, content)
                return []
        except Exception as ex:  # pylint: disable=broad-except
            logger.error("Error generating fact check suggestions: %s", ex)
            return []

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

    async def classify_message_nature(self, text: str) -> str:
        """Classify the message as safe or unsafe."""

        loop = asyncio.get_event_loop()
        try:
            create_completion = functools.partial(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Classify the following message as safe or unsafe. "
                            "Reply with 'safe' or 'unsafe' only.\n"
                            f"Message: {text}"
                        ),
                    }
                ],
                temperature=0,
                max_tokens=10,
            )

            response = await loop.run_in_executor(None, create_completion)

            content = response.choices[0].message.content or ""
            return "unsafe" if "unsafe" in content.lower() else "safe"
        except Exception as ex:  # pylint: disable=broad-except
            logger.error("Error classifying message nature: %s", {ex})
            return "safe"

    async def summarize_messages(self, messages: List[str]) -> str:
        """Summarize a collection of messages."""

        loop = asyncio.get_event_loop()
        try:
            joined_messages = "\n".join(messages)
            create_completion = functools.partial(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Summarize the following messages in a concise way:\n"
                            f"{joined_messages}"
                        ),
                    }
                ],
                temperature=0.5,
                max_tokens=150,
            )

            response = await loop.run_in_executor(None, create_completion)

            content = response.choices[0].message.content
            return content.strip() if content else ""
        except Exception as ex:  # pylint: disable=broad-except
            logger.error("Error summarizing messages: %s", {ex})
            return ""

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
