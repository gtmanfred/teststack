import json
import os

import click
import podman.errors


class Client:
    def __init__(self, **kwargs):
        self.client = podman.PodmanClient(**kwargs)

    def __del__(self):
        self.client.close()

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
        volumes = volumes or {}
        if mount_cwd is True:
            volumes.update(
                {
                    os.getcwd(): {
                        'bind': self.client.images.get(image).attrs['Config']['WorkingDir'],
                        'mode': 'rw',
                    },
                }
            )

        if ports:
            for port, hostport in ports.items():
                if not hostport:
                    ports[port] = None

        if not self.image_get(image):
            self.client.images.pull(image)

        return self.client.containers.run(
            name=name,
            image=image,
            detach=True,
            stream=stream,
            user='root',
            ports=ports or {},
            environment=environment or {},
            command=command,
            volumes=volumes,
        ).id

    def image_get(self, tag):
        try:
            return self.client.images.get(tag).id
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
        return self.client.images.build(path='.', dockerfile=dockerfile, tag=tag, nocache=rebuild, rm=True)

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
