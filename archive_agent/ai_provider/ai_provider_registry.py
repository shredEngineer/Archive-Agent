#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from archive_agent.ai_provider.AiProviderKeys import AiProviderKeys

from archive_agent.ai_provider.OpenAiProvider import OpenAiProvider
from archive_agent.ai_provider.OllamaProvider import OllamaProvider


ai_provider_registry = {

    "openai": {
        "class": OpenAiProvider,
        "defaults": {
            AiProviderKeys.AI_PROVIDER: "openai",
            AiProviderKeys.AI_SERVER_URL: "https://api.openai.com/v1",
            AiProviderKeys.AI_MODEL_CHUNK: "gpt-4o-2024-08-06",
            AiProviderKeys.AI_MODEL_EMBED: "text-embedding-3-small",
            AiProviderKeys.AI_MODEL_QUERY: "gpt-4o-2024-08-06",
            AiProviderKeys.AI_MODEL_VISION: "gpt-4o-2024-08-06",
            AiProviderKeys.AI_VECTOR_SIZE: 1536,
            AiProviderKeys.AI_TEMPERATURE_QUERY: 1.0,
        },
    },

    "ollama": {
        "class": OllamaProvider,
        "defaults": {
            AiProviderKeys.AI_PROVIDER: "ollama",
            AiProviderKeys.AI_SERVER_URL: "http://localhost:11434",
            AiProviderKeys.AI_MODEL_CHUNK: "deepseek-coder:6.7b-instruct",
            AiProviderKeys.AI_MODEL_EMBED: "nomic-embed-text",
            AiProviderKeys.AI_MODEL_QUERY: "deepseek-coder:6.7b-instruct",
            AiProviderKeys.AI_MODEL_VISION: "llava",
            AiProviderKeys.AI_VECTOR_SIZE: 768,
            AiProviderKeys.AI_TEMPERATURE_QUERY: 1.0,
        },
    },

}
