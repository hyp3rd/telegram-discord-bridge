"""This module handles the communication with the OpenAI API."""
import asyncio
import functools

import openai
import openai.error

from config import Config
from logger import app_logger

logger = app_logger()
config = Config()

openai.api_key = config.openai_api_key
openai.organization = config.openai_organization


async def analyze_message_and_generate_suggestions(text: str) -> str:
    """analyze the message text and seek for suggestions."""

    loop = asyncio.get_event_loop()
    try:
        create_completion = functools.partial(
            openai.Completion.create,
            model="text-davinci-003",
            prompt=(
                f"Given the message: '{text}', suggest related actions and correlated articles with links:\n"
                f"Related Actions:\n- ACTION1\n- ACTION2\n- ACTION3\n"
                f"Correlated Articles:\n1. ARTICLE1_TITLE - ARTICLE1_LINK\n"
                f"2. ARTICLE2_TITLE - ARTICLE2_LINK\n"
                f"3. ARTICLE3_TITLE - ARTICLE3_LINK\n"
            ),
            temperature=0,
            max_tokens=60,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )

        response = await loop.run_in_executor(None, create_completion)

        suggestion = response.choices[0].text.strip()
        return suggestion
    except openai.error.InvalidRequestError as ex:
        logger.error("Invalid request error: %s", {ex})
        return "Error generating suggestion: Invalid request."
    except openai.error.RateLimitError as ex:
        logger.error("Rate limit error: %s", {ex})
        return "Error generating suggestion: Rate limit exceeded."
    except openai.error.APIError as ex:
        logger.error("API error: %s", {ex})
        return "Error generating suggestion: API error."
    except Exception as ex:  # pylint: disable=broad-except
        logger.error("Error generating suggestion: %s", {ex})
        return "Error generating suggestion."


async def analyze_message_sentiment(text: str) -> str:
    """analyze the message text and seek for suggestions."""
    loop = asyncio.get_event_loop()
    try:
        prompt = None
        for prompt_line in config.openai_sentiment_analysis_prompt:
            prompt = f"{prompt} {prompt_line}\n"

        prompt = prompt.replace("#text_to_parse", text)

        logger.debug("openai_sentiment_analysis_prompt %s", prompt)

        create_completion = functools.partial(
            openai.Completion.create,
            model="text-davinci-003",
            prompt=(prompt),
            temperature=0.7,
            max_tokens=250,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )

        response = await loop.run_in_executor(None, create_completion)

        suggestion = response.choices[0].text.strip()
        return suggestion
    except openai.error.InvalidRequestError as ex:
        logger.error("Invalid request error: %s", {ex})
        return "Error generating suggestion: Invalid request."
    except openai.error.RateLimitError as ex:
        logger.error("Rate limit error: %s", {ex})
        return "Error generating suggestion: Rate limit exceeded."
    except openai.error.APIError as ex:
        logger.error("API error: %s", {ex})
        return "Error generating suggestion: API error."
    except Exception as ex:  # pylint: disable=broad-except
        logger.error("Error generating suggestion: %s", {ex})
        return "Error generating suggestion."
