"""
Combination configuration schema and data models.

* Ideally in the future this holds the configuration schema and the data models are seperated.
For the moment at least this defines the schema and moves away from freeform dictionaries everywhere.
** Configuration needs to support plugins. In a perfect world we'd have a system for plugins to register any extensions
they make to the configuration schema so that we can detect and warn the user when 'invalid' values are set
- nothing is more painful that bloated configurations with cargo-culted values that don't actually do anything -,
until then we have to allow any random configuration key to support plugin configurations.
"""
import typing
from dataclasses import dataclass, field

from .tests import Tests
from .service import Service


@dataclass
class ClientConfiguration:
    """
    Defines the client that will interact with your container engine/manager.

    name: identifier for a container framework.
        Teststack ships with built-in support for 'docker' and 'podman', but plugins can add others.
    prefix: Prefix to add to image name for all built containers.
        #TODO: Ask what the purpose of this is and why it lives in the client config.

    **All other configurations are dumped into 'kwargs'.
    See client specific configuration options for details.
    """

    name: str = "docker"
    prefix: str = ''
    kwargs: dict[str, typing.Any] = field(default_factory=dict)

    @classmethod
    def load(cls, raw_configuration: dict[str, typing.Any]):
        return cls(
            name=raw_configuration.pop("name", cls.__dataclass_fields__["name"].default),
            prefix=raw_configuration.pop("prefix", cls.__dataclass_fields__["prefix"].default),
            kwargs=raw_configuration,
        )


@dataclass
class Configuration:
    client: ClientConfiguration = field(default_factory=ClientConfiguration)
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
            kwargs["client"] = ClientConfiguration.load(raw_configuration["client"])
        if "tests" in raw_configuration:
            kwargs["tests"] = Tests.load(raw_configuration["tests"])
        if "services" in raw_configuration:
            kwargs["services"] = {k: Service.load(k, v) for k, v in raw_configuration["services"].items()}
        return cls(**kwargs)
