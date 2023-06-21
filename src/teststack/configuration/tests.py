import typing
from dataclasses import dataclass, field
from collections import OrderedDict


@dataclass
class Step:
    """
    Defines one step (command) to execute as part of the test run

    command: Command to execute. Can include the magic {posargs} string.
    requires: Names of other steps that _must_ be run before this one.
    check: Command to execute to check if the main command should run; supersedes requires.
        Useful to avoid re-running costly steps that do not need to be executed on every run.
    user: User to execute the command as.
    """

    name: str
    command: list[str]
    requires: list[str] = field(default_factory=list)
    check: str | None = None
    user: str | None = None

    @classmethod
    def load(cls, name: str, raw_configuration: dict[str, typing.Any] | list[str] | str) -> 'Step':
        if isinstance(raw_configuration, str):
            # A single command was given for this step configuration
            return cls(name=name, command=[raw_configuration])
        elif isinstance(raw_configuration, list):
            # A list of commands was given for this step configuration
            return cls(name=name, command=raw_configuration)

        # Standard configuration
        kwargs = {"name": name}
        if "command" in raw_configuration:
            # Handle command being allowed as either a string or list of strings
            if isinstance(raw_configuration["command"], str):
                kwargs["command"] = [raw_configuration["command"]]
            else:
                kwargs["command"] = raw_configuration["command"]
        if "requires" in raw_configuration:
            # Handle requires being allowed as either a string or list of strings
            if isinstance(raw_configuration["requires"], str):
                kwargs["requires"] = [raw_configuration["requires"]]
            else:
                kwargs["requires"] = raw_configuration["requires"]
        kwargs.update(
            {
                k: v
                for k, v in raw_configuration.items()
                if k not in ["command", "requires"] and k in cls.__dataclass_fields__  # Ignore extra fields for now
            }
        )
        return cls(**kwargs)


@dataclass
class Import:
    """
    Defines steps (commands) to execute when the test container is imported as a dependent service

    command: The main command to run for the container
    setup: A list of setup commands to run in the container
    """

    command: str = None
    setup: list[str] = field(default_factory=list)


@dataclass
class Tests:
    """
    Defines the test container configuration and the steps to execute
    inside that container as part of a test run.

    min_version: Minimum version of teststack that can run this configuration.
    mount: Whether to mount the current directory as a volume.
    copy: List of files to copy out of the test container when the `copy` command is run.
    command: Main process to run in test container. Overrides teststack default
        (Default is to run a tail -- sh -c 'trap \"trap - TERM; kill -s TERM -- -$$\" TERM; tail -f /dev/null & wait)
    steps: List of commands to execute (in order)
    environment: List of environmental variables and values to set in the container.
    ports: List of port mappings to set for the container <Container-Port>:<Host-Port>.
        Host port can be left blank to 'automap' to a free port.
    export: List of environment variables to export.
        (For example if another test imports this test container as a service)
    buildargs: Inject environmental variables into the build context.
        Useful for templating a Dockerfile without using Jinja
    import: Commands to run in the 'test' container when this teststack configuration is imported.
    """

    min_version: str | None = None
    mount: bool = True
    copy: list[str] = field(default_factory=list)
    command: str | None = None
    steps: OrderedDict[str, Step] = field(default_factory=OrderedDict)
    environment: dict[str, str] = field(default_factory=dict)
    ports: dict[str, str] = field(default_factory=dict)
    export: dict[str, str] = field(default_factory=dict)
    buildargs: dict[str, str] | None = None
    _import: Import = field(default_factory=Import)

    @classmethod
    def load(cls, raw_configuration: dict[str, typing.Any]) -> 'Tests':
        # Note: Can remove this if it's acceptable to add pydantic as a dependency
        kwargs = {}
        if "min_version" in raw_configuration:
            # Handle striping a leading 'v'
            kwargs["min_version"] = raw_configuration["min_version"].lstrip('v')
        if "steps" in raw_configuration:
            kwargs["steps"] = {k: Step.load(k, v) for k, v in raw_configuration["steps"].items()}
        if "import" in raw_configuration:
            kwargs["_import"] = Import(**raw_configuration["import"])
        kwargs.update(
            {
                k: v
                for k, v in raw_configuration.items()
                if k not in ["min_version", "steps", "import"]
                and k in cls.__dataclass_fields__  # Ignore extra fields for now
            }
        )
        return cls(**kwargs)
