import typing
from dataclasses import dataclass
from collections import OrderedDict
from .service import Import


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
    requires: list[str] | None = None
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
        kwargs.update({k: v for k, v in raw_configuration if k not in ["command", "requires"]})
        return cls(**kwargs)


@dataclass
class Tests:
    """
    Defines the test container configuration and the steps to execute
    inside that container as part of a test run.

    min_version: Minimum version of teststack that can run this configuration.
    copy: List of files to copy out of the test container when the `copy` command is run.
    steps: List of commands to execute (in order)
    environment: List of environmental variables and values to set in the container.
    ports: List of port mappings to set for the container <Container-Port>:<Host-Port>.
        Host port can be left blank to 'automap' to a free port.
    export: List of environment variables to export.
        (For example if another test imports this test container as a service)
    buildargs: Inject environmental variables into the build context.
        Useful for templating a Dockerfile without using Jinja
    import: List of teststack configurations to import as dependent services.
        Useful for setting up 'clusters' to test against.
    """

    min_version: str | None = None
    copy: list[str] | None = None
    steps: OrderedDict[str, Step] | None = None
    environment: dict[str, str] | None = None
    ports: dict[str, str] | None = None
    export: dict[str, str] | None = None
    buildargs: dict[str, str] | None = None
    _import: dict[str, Import | list[str] | str] | None = None

    @classmethod
    def load(cls, raw_configuration: dict[str, typing.Any]) -> 'Tests':
        # Note: Can remove this if it's acceptable to add pydantic as a dependency
        kwargs = {}
        if "steps" in raw_configuration:
            kwargs["steps"] = {k: Step.load(k, v) for k, v in raw_configuration["steps"]}
        if "import" in raw_configuration:
            kwargs["import"] = Import(**raw_configuration["import"])
        kwargs.update({k: v for k, v in raw_configuration if k not in ["steps", "import"]})
        return cls(**kwargs)
