import typing
from dataclasses import dataclass, field

from .tests import Tests
from .service import Service


@dataclass
class Client:
    name: str = "docker"
    prefix: str | None = None


@dataclass
class Configuration:
    client: Client = field(default_factory=Client)
    tests: Tests = field(default_factory=Tests)
    services: dict[str, Service] = field(default_factory=list)

    @classmethod
    def load(cls, raw_configuration: dict[str, typing.Any]):
        # Note: Can remove this if it's acceptable to add pydantic as a dependency
        kwargs = {
            k: v for k, v in raw_configuration.items() if k in cls.__dataclass_fields__  # Ignore extra fields for now
        }
        # Handle loading
        if "client" in raw_configuration:
            kwargs["client"] = Client(**raw_configuration["client"])
        if "tests" in raw_configuration:
            kwargs["tests"] = Tests.load(raw_configuration["tests"])
        if "services" in raw_configuration:
            kwargs["services"] = {k: Service.load(k, v) for k, v in raw_configuration["services"].items()}
        return cls(**kwargs)
