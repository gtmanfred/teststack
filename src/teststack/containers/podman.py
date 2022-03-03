"""
Client for interfacing with podman.

To enable using podman as the container interface, specify the following section
in the ``teststack.toml``

.. code-block:: toml

    [client]
    name = "podman"

There is an extra provided to install the ``podman`` dependency.

.. code-block:: shell

    python3 -m pip install teststack[podman]
"""
import json
import os
import platform
import socket
import subprocess

import click
import podman.errors


class Client:
    def __init__(self, machine_name=None, **kwargs):
        if machine_name is not None:
            kws = self._get_connection(machine_name)
            kws.update(kwargs)
        elif platform.system() == 'Darwin':
            kws = self._get_connection('*')
            kws.update(kwargs)
        else:
            kws = kwargs

        if kws:
            self.client = podman.PodmanClient(**kws)
        else:
            self.client = podman.from_env()

    def _process_image_shortname(self, name, default='docker.io'):
        if '/' in name:
            domain = name.split('/')[0]
            try:
                socket.getaddrinfo(domain, 443)
                return name
            except socket.gaierror:
                pass
        return f'docker.io/{name}'

    def _get_connection(self, name):
        connections = subprocess.check_output(
            [
                'podman',
                'system',
                'connection',
                'list',
                '--format=json',
            ]
        )

        if connections:
            connections = json.loads(connections)
        else:
            return {}

        for connection in connections:
            if connection['Name'].endswith(name):
                return {
                    'base_url': f'http+{connection["URI"]}',
                    'identity': connection['Identity'],
                }
        return {}

    def end_container(self, name):
        try:
            container = self.client.containers.get(name)
        except podman.errors.NotFound:
            return
        try:
            container.stop()
            container.wait()
        except podman.errors.APIError:
            pass
        finally:
            container.remove(v=True)

    def container_get(self, name):
        try:
            return self.client.containers.get(name).id
        except podman.errors.NotFound:
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
        mounts = volumes or []
        if mount_cwd is True:
            mounts.append(
                {
                    'source': os.getcwd(),
                    'target': self.client.images.get(image).attrs['Config']['WorkingDir'],
                    'type': 'bind',
                }
            )

        if command is True:
            command = ['tail', '-f', '/dev/null']

        if ports:
            for port, hostport in ports.items():
                if not hostport:
                    ports[port] = None

        if not self.image_get(image):
            self.client.images.pull(self._process_image_shortname(image))

        container = self.client.containers.create(
            name=name,
            image=image,
            detach=True,
            stream=stream,
            ports=ports or {},
            environment=environment or {},
            command=command,
            mounts=mounts,
        )

        container.start()
        container.wait(condition="running")

        return container.id

    def start(self, name):
        container = self.container_get(name)
        self.client.containers.get(container).start()

    def image_get(self, tag):
        try:
            return self.client.images.get(self._process_image_shortname(tag)).id
        except podman.errors.ImageNotFound:
            return None

    def run_command(self, container, command):
        container = self.client.containers.get(container)
        click.echo(click.style(f'Run Command: {command}', fg='green'))
        socket = container.exec_run(
            cmd=command,
            tty=True,
            socket=True,
        )

        for line in socket.output:
            click.echo(line, nl=False)

    def build(self, dockerfile, tag, rebuild):
        image, _ = self.client.images.build(path='.', dockerfile=dockerfile, tag=tag, nocache=rebuild, rm=True)
        return image.id

    def get_container_data(self, name, inside=False):
        data = {}
        try:
            container = self.client.containers.get(name)
        except podman.errors.NotFound:
            return None
        data['HOST'] = container.attrs['NetworkSettings']['IPAddress'] if inside else 'localhost'
        for port, port_data in container.attrs['NetworkSettings']['Ports'].items():
            if inside:
                data[f'PORT;{port}'] = port.split('/')[0]
            elif port_data:
                data[f'PORT;{port}'] = port_data[0]['HostPort']
        return data

    def exec(self, container):
        os.execvp('podman', ['podman', 'exec', '-ti', container, 'bash'])
