"""Contextual analysis of the anti-spam of the bridge."""

from telethon import TelegramClient
from telethon.tl.types import Message

from bridge.config import Config
from bridge.logger import Logger
from core import SingletonMeta

config = Config.get_instance()
logger = Logger.get_logger(config.application.name)


# pylint: disable=too-few-public-methods
class ContextualAnalysis(metaclass=SingletonMeta):
    """Contextual analysis class."""

    def __init__(self):
        """Initialize the class and lazily import NLTK resources."""
        # pylint: disable=import-outside-toplevel
        import nltk
        from nltk import pos_tag
        from nltk.corpus import stopwords, wordnet
        from nltk.stem import WordNetLemmatizer
        from nltk.tokenize import RegexpTokenizer

        nltk.download("punkt")
        nltk.download("stopwords")
        nltk.download("averaged_perceptron_tagger")
        nltk.download("wordnet")

        self.pos_tag = pos_tag
        self.stop_words = set(stopwords.words("english"))
        self.tokenizer = RegexpTokenizer(r"\w+")
        self.lemmatizer = WordNetLemmatizer()
        self.wordnet = wordnet

    def __extract_keywords(self, text):
        """Extract keywords from a text using advanced techniques."""

        word_tokens = self.tokenizer.tokenize(text)
        pos_tags = self.pos_tag(word_tokens)

        keywords = [
            self.lemmatizer.lemmatize(word, pos=self.__get_wordnet_pos(pos))
            for word, pos in pos_tags
            if word.lower() not in self.stop_words and word.isalpha()
        ]
        return keywords

    async def is_relevant_message(
        self, telegram_message: Message, channel_id: int, tgc: TelegramClient
    ) -> bool:
        """Check if a message is relevant based on contextual analysis."""
        logger.warning("Checking if message is relevant")
        recent_messages = await tgc.get_messages(channel_id, limit=50)

        # Process messages in smaller context windows
        context_windows = self.__create_context_windows(recent_messages, window_size=10)

        # Extract keywords from the new message
        new_message_keywords = self.__extract_keywords(telegram_message.text)

        # Check each context window for relevance
        for window in context_windows:
            window_keywords = self.__extract_keywords(
                " ".join([msg.text for msg in window])
            )
            if any(keyword in window_keywords for keyword in new_message_keywords):
                return True

        return False

    def __create_context_windows(self, messages, window_size=10):
        """Create smaller context windows from a list of messages."""
        return [
            messages[i : i + window_size] for i in range(0, len(messages), window_size)
        ]

    def __get_wordnet_pos(self, treebank_tag):
        """Convert treebank POS tags to WordNet POS tags."""
        if treebank_tag.startswith("J"):
            return self.wordnet.ADJ
        if treebank_tag.startswith("V"):
            return self.wordnet.VERB
        if treebank_tag.startswith("N"):
            return self.wordnet.NOUN
        if treebank_tag.startswith("R"):
            return self.wordnet.ADV

        return self.wordnet.NOUN  # Default to NOUN
