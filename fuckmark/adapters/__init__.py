from .base import AdapterRegistry, AdapterSignals, WatermarkAdapter
from .deepmind_reference import (
    ADAPTER_ID as DEEPMIND_REFERENCE_ADAPTER_ID,
    ALGORITHM_VERSION as DEEPMIND_REFERENCE_ALGORITHM_VERSION,
    SOURCE_PIN as DEEPMIND_REFERENCE_SOURCE_PIN,
    DeepMindReferenceAdapter,
    DeepMindReferenceConfig,
    create_deepmind_reference_adapter,
)
from .huggingface_synthid import (
    ADAPTER_ID as HUGGINGFACE_SYNTHID_ADAPTER_ID,
    ALGORITHM_VERSION as HUGGINGFACE_SYNTHID_ALGORITHM_VERSION,
    SOURCE_PIN as HUGGINGFACE_SYNTHID_SOURCE_PIN,
    HuggingFaceSynthIDAdapter,
    HuggingFaceSynthIDConfig,
    create_huggingface_synthid_adapter,
)


def default_adapter_registry() -> AdapterRegistry:
    registry = AdapterRegistry()
    registry.register(DEEPMIND_REFERENCE_ADAPTER_ID, create_deepmind_reference_adapter)
    registry.register(HUGGINGFACE_SYNTHID_ADAPTER_ID, create_huggingface_synthid_adapter)
    return registry


__all__ = [
    "AdapterRegistry",
    "AdapterSignals",
    "DEEPMIND_REFERENCE_ADAPTER_ID",
    "DEEPMIND_REFERENCE_ALGORITHM_VERSION",
    "DEEPMIND_REFERENCE_SOURCE_PIN",
    "DeepMindReferenceAdapter",
    "DeepMindReferenceConfig",
    "HUGGINGFACE_SYNTHID_ADAPTER_ID",
    "HUGGINGFACE_SYNTHID_ALGORITHM_VERSION",
    "HUGGINGFACE_SYNTHID_SOURCE_PIN",
    "HuggingFaceSynthIDAdapter",
    "HuggingFaceSynthIDConfig",
    "WatermarkAdapter",
    "create_deepmind_reference_adapter",
    "create_huggingface_synthid_adapter",
    "default_adapter_registry",
]
