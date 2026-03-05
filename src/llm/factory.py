"""LLM provider factory with registry pattern."""

from typing import Dict, Optional, Type

from loguru import logger

from src.llm.base import BaseLLMProvider


class LLMProviderFactory:
    """Registry-based factory for LLM providers."""

    _registry: Dict[str, Type[BaseLLMProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: Type[BaseLLMProvider]) -> None:
        """Register a provider class.

        Args:
            name: Provider name (e.g., 'groq', 'openai')
            provider_class: The provider class to register
        """
        cls._registry[name.lower()] = provider_class
        logger.debug(f"Registered LLM provider: {name}")

    @classmethod
    def create(
        cls,
        name: str,
        api_key: str,
        model: str,
        temperature: float = 0.0,
    ) -> BaseLLMProvider:
        """Create a provider instance.

        Args:
            name: Provider name
            api_key: API key
            model: Model name
            temperature: Temperature setting

        Returns:
            Initialized provider instance

        Raises:
            ValueError: If provider name is not registered
        """
        name_lower = name.lower()
        if name_lower not in cls._registry:
            available = ", ".join(cls._registry.keys()) or "none"
            raise ValueError(f"Unknown LLM provider: '{name}'. Available: {available}")
        return cls._registry[name_lower](
            api_key=api_key,
            model=model,
            temperature=temperature,
        )

    @classmethod
    def from_config(cls, settings) -> Optional[BaseLLMProvider]:
        """Create a provider from application settings.

        Returns None if LLM is disabled (no provider configured).

        Args:
            settings: Settings instance with llm_provider, llm_api_key, etc.

        Returns:
            Provider instance or None
        """
        if not settings.llm_provider:
            logger.info("LLM provider not configured, running without LLM support")
            return None

        if not settings.llm_api_key:
            logger.warning(f"LLM provider '{settings.llm_provider}' configured but no API key set")
            return None

        # Import providers to trigger auto-registration
        import src.llm.providers  # noqa: F401

        try:
            provider = cls.create(
                name=settings.llm_provider,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                temperature=settings.llm_temperature,
            )
            logger.info(
                f"LLM provider initialized: {provider.provider_name} "
                f"(model: {settings.llm_model})"
            )
            return provider
        except ValueError as e:
            logger.error(str(e))
            return None

    @classmethod
    def available_providers(cls) -> list:
        """Return list of registered provider names."""
        return list(cls._registry.keys())
