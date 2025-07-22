#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from archive_agent.ai_provider.AiProviderKeys import AiProviderKeys

from archive_agent.ai_provider.OpenAiProvider import OpenAiProvider
from archive_agent.ai_provider.OllamaProvider import OllamaProvider
from archive_agent.ai_provider.LMStudioProvider import LMStudioProvider


ai_provider_registry = {
    # first entry is used as default for new profiles

    "openai": {
        "class": OpenAiProvider,
        "defaults": {
            AiProviderKeys.AI_PROVIDER: "openai",
            AiProviderKeys.AI_SERVER_URL: "https://api.openai.com/v1",
            AiProviderKeys.AI_MODEL_CHUNK: "gpt-4o-2024-08-06",
            AiProviderKeys.AI_MODEL_EMBED: "text-embedding-3-small",
            AiProviderKeys.AI_MODEL_RERANK: "gpt-4o-2024-08-06",
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
            AiProviderKeys.AI_MODEL_CHUNK: "llama3.1:8b",
            AiProviderKeys.AI_MODEL_EMBED: "nomic-embed-text:v1.5",
            AiProviderKeys.AI_MODEL_RERANK: "llama3.1:8b",
            AiProviderKeys.AI_MODEL_QUERY: "llama3.1:8b",
            AiProviderKeys.AI_MODEL_VISION: "llava:7b-v1.6",
            AiProviderKeys.AI_VECTOR_SIZE: 768,
            AiProviderKeys.AI_TEMPERATURE_QUERY: 1.0,
        },
    },

    "lmstudio": {
        "class": LMStudioProvider,
        "defaults": {
            AiProviderKeys.AI_PROVIDER: "lmstudio",
            AiProviderKeys.AI_SERVER_URL: "http://localhost:1234/v1",
            AiProviderKeys.AI_MODEL_CHUNK: "meta-llama-3.1-8b-instruct",
            AiProviderKeys.AI_MODEL_EMBED: "text-embedding-nomic-embed-text-v1.5",
            AiProviderKeys.AI_MODEL_RERANK: "meta-llama-3.1-8b-instruct",
            AiProviderKeys.AI_MODEL_QUERY: "meta-llama-3.1-8b-instruct",
            AiProviderKeys.AI_MODEL_VISION: "llava-v1.5-7b",
            AiProviderKeys.AI_VECTOR_SIZE: 768,
            AiProviderKeys.AI_TEMPERATURE_QUERY: 1.0,
        },
    },

    # TODO: Add Gemini, Grok, Claude providers

}
