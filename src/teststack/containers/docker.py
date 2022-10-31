import json
import os
import select
import socket
import sys

import click
import docker.errors

from ..utils import read_from_stdin


class Client:
    def __init__(self, **kwargs):
        context = docker.ContextAPI.get_current_context()
        if context.name == 'default':
            self.client = docker.from_env()
        else:
            self.client = docker.DockerClient(
                base_url=context.Host,
                tls=context.TLSConfig,
            )

    def end_container(self, name):
        try:
            container = self.client.containers.get(name)
        except docker.errors.NotFound:
            return
        container.stop()
        container.wait()
        container.remove(v=True)

    def container_get(self, name):
        try:
            return self.client.containers.get(name).id
        except docker.errors.NotFound:
            return None

    def container_get_current_image(self, name):
        container = self.container_get(name)
        if container:
            return self.client.containers.get(container).image.id
        return None

    def run(
        self,
        name,
        image,
        ports=None,
        command=None,
        environment=None,
        stream=False,
        user=None,
        volumes=None,
        mount_cwd=False,
    ):
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
        if command is True:  # pragma: no branch
            command = "sh -c 'trap \"trap - TERM; kill -s TERM -- -$$\" TERM; tail -f /dev/null & wait'"

        return self.client.containers.run(
            name=name,
            image=image,
            detach=True,
            stream=stream,
            user=user,
            ports=ports or {},
            command=command,
            environment=environment or {},
            volumes=volumes,
        ).id

    def start(self, name):
        self.client.containers.get(name).start()

    def status(self, name):
        try:
            return self.client.containers.get(name).status
        except docker.errors.NotFound:
            return 'notfound'

    def image_get(self, tag):
        try:
            return self.client.images.get(tag).id
        except docker.errors.ImageNotFound:
            return None

    def run_command(self, container, command, user=None):
        container = self.client.containers.get(container)
        click.echo(click.style(f'Run Command: {command}', fg='green'))
        exec_id = container.client.api.exec_create(
            container.id,
            command,
            stdin=True,
            tty=True,
            user=user or '',
        )['Id']

        sock = container.client.api.exec_start(
            exec_id,
            tty=True,
            socket=True,
        )
        sock = getattr(sock, '_sock', sock)

        with read_from_stdin() as fd:
            if fd is not None:  # pragma: no cover
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

    def build(self, dockerfile, tag, rebuild):
        for data in self.client.api.build(
            path='.', dockerfile=dockerfile, tag=tag, nocache=rebuild, decode=True, rm=True
        ):
            if 'stream' in data:
                click.echo(data['stream'], nl=False)

    def get_container_data(self, name, inside=False):
        data = {}
        try:
            container = self.client.containers.get(name)
        except docker.errors.NotFound:
            return None
        self.start(name)
        data['HOST'] = container.attrs['NetworkSettings']['IPAddress'] if inside else 'localhost'
        for port, port_data in container.attrs['NetworkSettings']['Ports'].items():
            if inside:
                data[f'PORT;{port}'] = port.split('/')[0]
            elif port_data:
                data[f'PORT;{port}'] = port_data[0]['HostPort']
        return data

    def exec(self, container):
        os.execvp('docker', ['docker', 'exec', '-ti', container, 'bash'])
