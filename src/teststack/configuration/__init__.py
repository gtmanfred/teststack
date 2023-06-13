import typing
from dataclasses import dataclass, field

from .tests import Tests
from .service import Service


@dataclass
class Configuration:
    client: str = "docker"
    tests: Tests | None = None
    services: list[Service] = field(default_factory=list)

    @classmethod
    def load(cls, raw_configuration: dict[str, typing.Any]):
        # Note: Can remove this if it's acceptable to add pydantic as a dependency
        kwargs = {}
        if "tests" in raw_configuration:
            kwargs["tests"] = Tests.load(raw_configuration["tests"])
        if "services" in raw_configuration:
            kwargs["services"] = Service.load(raw_configuration["services"])
        kwargs.update({k: v for k, v in raw_configuration if k not in ["tests", "services"]})
        return cls(**kwargs)
