import io
import os
import select
import shutil
import socket
import subprocess
import sys
import tarfile

import click
import docker.errors

from . import Client as ClientProtocol
from . import Mount
from ..utils import read_from_stdin


class Client(ClientProtocol):
    def __init__(self, **kwargs):
        context = docker.ContextAPI.get_current_context()
        if context.name == 'default':  # pragma: no branch
            self.client = docker.from_env(**kwargs)
        else:
            self.client = docker.DockerClient(
                base_url=context.Host,
                tls=context.TLSConfig,
                **kwargs,
            )  # pragma: no cover

    def end_container(self, name: str) -> None:
        try:
            container = self.client.containers.get(name)
        except docker.errors.NotFound:
            return
        container.stop()
        container.wait()
        container.remove(v=True)

    def container_get(self, name: str) -> str | None:
        try:
            return self.client.containers.get(name).id
        except docker.errors.NotFound:
            return None

    def container_get_current_image(self, name: str) -> str | None:
        container = self.container_get(name)
        if container:
            image = self.client.containers.get(container).image
            if image:
                return image.id
        return None

    def network_get(self, names=None, ids=None):
        networks = self.client.networks.list(names=names or [], ids=ids or [])
        if not networks:
            return None
        return networks[0]

    def network_create(self, name):
        return self.client.networks.create(name, driver="bridge")

    def network_prune(self):
        self.client.networks.prune()

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
        networkobj = self.network_get(names=[network])
        if networkobj is None:
            self.network_create(network)

        if mount_cwd is True:
            volumes = volumes or {}
            volumes.update(
                {
                    os.getcwd(): {
                        'bind': self.client.images.get(image).attrs['Config']['WorkingDir'],
                        'mode': 'rw',
                    },
                }
            )

        entrypoint = {}
        if command:
            # May need to set "entrypoint: /bin/sh"
            entrypoint = {"command": command}

        return self.client.containers.run(
            name=name,
            image=image,
            detach=True,
            stream=stream,
            user=user,
            ports=ports or {},
            environment=environment or {},
            volumes=volumes,
            network=network,
            hostname=service,
            **entrypoint,
        ).id  # type: ignore

    def cp(self, name: str, src: str):
        container = self.client.containers.get(name)

        if not src.startswith('/'):
            workdir = container.attrs['Config']['WorkingDir']
            src_path = '/'.join([workdir.rstrip('/'), src])
        else:
            src_path, src = src, os.path.basename(src)

        try:
            data, _ = container.get_archive(src_path, chunk_size=1)
        except docker.errors.NotFound:
            return False
        archive = tarfile.TarFile(fileobj=io.BytesIO(b''.join(data)))
        archive.extract(src)
        return True

    @staticmethod
    def _get_network_id(network):
        if 'NetworkId' in network:
            return network['NetworkId']
        if 'NetworkID' in network:
            return network['NetworkID']
        return None

    def start(self, name: str) -> None:
        container = self.client.containers.get(name)
        for network_name, network in container.attrs['NetworkSettings']['Networks'].items():
            if not self.network_get(ids=[self._get_network_id(network)]):
                if container.id is not None:
                    self.client.api.disconnect_container_from_network(container.id, network_name, force=True)
                if not self.network_get(names=[network_name]):
                    self.network_create(name=network_name)
                self.network_get(names=[network_name]).connect(container)
        container.start()

    def status(self, name: str) -> str:
        try:
            return self.client.containers.get(name).status
        except docker.errors.NotFound:
            return 'notfound'

    def logs(self, name: str) -> str:
        try:
            return self.client.containers.get(name).logs()
        except docker.errors.NotFound:
            return 'notfound'

    def image_get(self, tag: str) -> str | None:
        try:
            return self.client.images.get(tag).id
        except docker.errors.ImageNotFound:
            return None

    def run_command(self, container: str, command: str, user: str | None = None) -> int:
        container = self.client.containers.get(container)
        click.echo(click.style(f'Run Command: {command}', fg='green'))
        terminal = shutil.get_terminal_size()
        exec_id = container.client.api.exec_create(
            container.id,
            command,
            stdin=True,
            tty=True,
            environment={
                'COLUMNS': terminal.columns or 80,
                'LINES': terminal.columns or 24,
            },
            user=user or '',
        )['Id']

        sock = container.client.api.exec_start(
            exec_id,
            tty=True,
            socket=True,
        )

        with read_from_stdin() as fd:
            if fd is not None:  # pragma: no cover
                sock = getattr(sock, '_sock', sock)
                BREAK = False
                while not BREAK:
                    reads, _, _ = select.select([sock, fd], [], [], 0.0)
                    for read in reads:
                        if isinstance(read, socket.socket):
                            line = read.recv(4096)
                            if not line:
                                BREAK = True
                            click.echo(line, nl=False)
                        else:
                            sock.send(sys.stdin.read(1).encode('utf-8'))
            else:
                for line in sock:
                    click.echo(line, nl=False)
        return container.client.api.exec_inspect(exec_id)['ExitCode']

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
        command = [
            "docker",
            "build",
            f"--file={directory}/{dockerfile}",
            f"--tag={tag}",
            "--rm",
            directory,
        ]
        if stage is not None:
            command.append(f"--target={stage}")
        if buildargs is not None:
            command.extend([f"--build-arg={key}={value}" for key, value in buildargs.items()])
        if rebuild is True:
            command.extend(["--no-cache", "--pull"])
        if secrets is not None:
            for name, mount in secrets.items():
                source = os.path.expanduser(mount.source)
                command.append(f"--secret=id={name},source={source}")
        subprocess.run(command)

    def get_container_data(self, name, network, inside=False):
        data = {}
        try:
            container = self.client.containers.get(name)
        except docker.errors.NotFound:
            return None
        self.start(name)
        data['HOST'] = container.attrs['NetworkSettings']['Networks'][network]['IPAddress'] if inside else 'localhost'
        for port, port_data in container.attrs['NetworkSettings']['Ports'].items():
            if inside:
                data[f'PORT;{port}'] = port.split('/')[0]
            elif port_data:
                data[f'PORT;{port}'] = port_data[0]['HostPort']
        return data

    def exec(self, container, user=None, command=None):
        cmd = ['docker', 'exec', '-ti']
        if user is not None:
            cmd.extend(['-u', user])
        cmd.append(container)
        if command is not None:
            cmd.extend(command)
        else:
            cmd.extend(['bash'])
        os.execvp('docker', cmd)  # pragma: no cover
