from typing import Protocol

from teststack.configuration.service import Mount


class Client(Protocol):
    def __init__(self, **kwargs):
        ...

    def end_container(self, name: str) -> None:
        """Halt the named container"""
        ...

    def container_get(self, name: str) -> str | None:
        """Return the id of the named container or None if the name was not found"""
        ...

    def container_get_current_image(self, name: str) -> str | None:
        """Return the id of the named container's image or None if the name was not found"""
        ...

    def run(
        self,
        name: str,
        image: str,
        ports: dict[str, str] | None = None,
        command: str | None = None,
        environment: dict[str, str] | None = None,
        stream: bool = False,
        user: str | None = None,
        volumes: dict[str, Mount] | None = None,
        mount_cwd: bool = False,
        network: str = 'bridge',
        service: str = 'tests',
    ):
        ...

    def start(self, name: str) -> None:
        ...

    def status(self, name: str) -> str:
        ...

    def logs(self, name: str) -> str:
        ...

    def image_get(self, tag: str) -> str | None:
        ...

    def run_command(self, container: str, command: str, user: str | None = None) -> int:
        ...

    def build(
        self,
        dockerfile: str,
        tag: str,
        rebuild: bool,
        directory: str = '.',
        buildargs: dict[str, str] | None = None,
        secrets: dict[str, Mount] | None = None,
        stage=None,
    ) -> None:
        ...

    def get_container_data(self, name: str, network: str, inside: bool = False) -> dict[str, str]:
        ...

    def exec(self, container: str, user: str | None = None, command: str | None = None) -> None:
        ...
