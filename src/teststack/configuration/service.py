import typing
from dataclasses import dataclass


@dataclass
class Import:
    """
    Defines a repository to pull a teststack configuration from.

    repo: Path or url to a directory with a teststack.toml file
    ref: Reference, commit, branch, or tag to use if the repo is a git repository.
    """

    repo: str
    ref: str | None = None


@dataclass
class Service:
    """
    Defines a 'service' container that the tests to run require.

    image: Docker image to use for the container
    build: Dockerfile to use to build an image to use for the container
    ports: Container ports to forward/map. <Container-Port>:<Host-Port>
        Host port can be left blank to 'auto-map' to a free port.
    environment: Environmental variables to inject into this container.
    export: Environmental variables to export.
        These will be injected into the test container.
    buildargs: Inject environmental variables into the build context.
        Useful for templating a Dockerfile without using Jinja
    import: Repository to pull a teststack configuration for this service.
    """

    name: str
    image: str | None = None
    build: str | None = None
    ports: dict[str, str] | None = None
    environment: dict[str, str] | None = None
    export: dict[str, str] | None = None
    buildargs: dict[str, str] | None = None
    _import: dict[str, Import] | None = None

    @classmethod
    def load(cls, name: str, raw_configuration: dict[str, typing.Any]) -> 'Service':
        # Note: Can remove this if it's acceptable to add pydantic as a dependency
        kwargs = {"name": name}
        if "import" in raw_configuration:
            kwargs["_import"] = Import(**raw_configuration["import"])
        kwargs.update(
            {
                k: v
                for k, v in raw_configuration.items()
                if k not in ["import"] and k in cls.__dataclass_fields__  # Ignore extra fields for now
            }
        )
        return cls(**kwargs)