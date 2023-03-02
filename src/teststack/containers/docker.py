import io
import os
import select
import shutil
import socket
import sys
import tarfile

import click
import docker.errors

from ..utils import read_from_stdin


class Client:
    def __init__(self, **kwargs):
        context = docker.ContextAPI.get_current_context()
        if context.name == 'default':  # pragma: no branch
            self.client = docker.from_env()
        else:
            self.client = docker.DockerClient(
                base_url=context.Host,
                tls=context.TLSConfig,
            )  # pragma: no cover

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

    def network_get(self, name):
        networks = self.client.networks.list(names=[name])
        if not networks:
            return None
        return networks[0]

    def network_create(self, name):
        return self.client.networks.create(name, driver="bridge")

    def network_prune(self):
        self.client.networks.prune()

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
        network='bridge',
        service='tests',
    ):
        networkobj = self.network_get(network)
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
            network=network,
            hostname=service,
        ).id

    def cp(self, name, src):
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

    def start(self, name):
        container = self.client.containers.get(name)
        for network_name, network in container.attrs['NetworkSettings']['Networks'].items():
            if not self.network_get(name=network_name):
                self.client.api.disconnect_container_from_network(container.id, network['NetworkId'], force=True)
                self.network_create(name=network_name).connect(container)
        container.start()

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

    def build(self, dockerfile, tag, rebuild, directory='.', buildargs=None):
        for data in self.client.api.build(
            path=directory,
            dockerfile=dockerfile,
            tag=tag,
            nocache=rebuild,
            pull=rebuild,
            decode=True,
            rm=True,
            buildargs=buildargs or {},
        ):
            if 'stream' in data:
                click.echo(data['stream'], nl=False)

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

    def exec(self, container, user=None):
        command = ['docker', 'exec', '-ti']
        if user is not None:
            command.extend(['-u', user])
        command.extend([container, 'bash'])
        os.execvp('docker', command)  # pragma: no cover
