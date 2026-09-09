"""One place that builds the language model.

Every agent asks for its model here, so switching provider or model is a
single change rather than one per agent.
"""

import config

_MISSING_KEY = (
    "GROQ_API_KEY is not set. Copy .env.example to .env and paste your own "
    "Groq key from console.groq.com. The .env file is gitignored."
)


def get_llm(temperature: float = 0.0):
    """Return a chat model. Raises RuntimeError when no key is configured."""
    if not config.GROQ_API_KEY:
        raise RuntimeError(_MISSING_KEY)

    from langchain_groq import ChatGroq

    return ChatGroq(
        model=config.GROQ_MODEL,
        api_key=config.GROQ_API_KEY,
        temperature=temperature,
    )
