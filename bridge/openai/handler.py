"""This module handles the communication with the OpenAI API."""
import asyncio
import copy
import functools

import openai

from bridge.config import Config
from bridge.logger import Logger
from core import SingletonMeta

config = Config.get_instance()
logger = Logger.get_logger(config.application.name)


class OpenAIHandler(metaclass=SingletonMeta):
    """OpenAI handler class."""

    openai.api_key = config.openai.api_key
    openai.organization = config.openai.organization

    @staticmethod
    async def analyze_message_and_generate_suggestions(text: str) -> str:
        """analyze the message text and seek for suggestions."""

        prompt = copy.deepcopy(config.openai.sentiment_analysis_prompt)
        prompt.append({"role":"user","content":text})

        loop = asyncio.get_event_loop()
        try:
            create_completion = functools.partial(
                openai.ChatCompletion.create,
                model=config.openai.model,
                temperature=config.openai.temperature,
                max_tokens=256,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
                messages=(prompt)
            )

            response = await loop.run_in_executor(None, create_completion)

            suggestion = response.choices[0].message.content # type: ignore # pylint: disable=no-member
            logger.debug("openai_sentiment_analysis_prompt result %s", suggestion)
            return suggestion
        except openai.InvalidRequestError as ex:  # pylint: disable=no-member
            logger.error("Invalid request error: %s", {ex})
            return "Error generating suggestion: Invalid request."
        except openai.APIError as ex:
            logger.error("API error: %s", {ex})
            return "Error generating suggestion: API error."
        except Exception as ex:  # pylint: disable=broad-except
            logger.error("Error generating suggestion: %s", {ex})
            return "Error generating suggestion."

    @staticmethod
    async def analyze_message_sentiment(text: str) -> str:
        """analyze the message text and seek for suggestions."""
        loop = asyncio.get_event_loop()
        try:
            prompt = copy.deepcopy(config.openai.sentiment_analysis_prompt)
            prompt.append({"role":"user","content":text})

            create_completion = functools.partial(
                openai.chat.completions.create,
                model=config.openai.model,
                temperature=config.openai.temperature,
                max_tokens=256,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
                messages=(prompt)
            )

            response = await loop.run_in_executor(None, create_completion)

            suggestion = response.choices[0].message.content # type: ignore # pylint: disable=no-member
            logger.debug("openai_sentiment_analysis_prompt result %s", suggestion)
            return suggestion
        #except openai.InvalidRequestError as ex:  # pylint: disable=no-member
        #    logger.error("Invalid request error: %s", {ex})
        #    return "Error generating suggestion: Invalid request."
        except openai.APIError as ex:
            logger.error("API error: %s", {ex})
            return "Error generating suggestion: API error."
        except Exception as ex:  # pylint: disable=broad-except
            logger.error("Error generating suggestion: %s", {ex})
            return "Error generating suggestion."
