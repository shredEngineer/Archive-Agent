#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.


class AiProviderError(Exception):
    """
    AI provider error (retryable).
    """
    pass


class AiProviderMaxTokensError(Exception):
    """
    AI provider error: model hit max tokens (non-retryable).
    Retrying with the same input will produce the same truncation.
    """
    pass
