import json
import os

import click
import docker.errors


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

    def image_get(self, tag):
        try:
            return self.client.images.get(tag).id
        except docker.errors.ImageNotFound:
            return None

    def run_command(self, container, command):
        container = self.client.containers.get(container)
        click.echo(click.style(f'Run Command: {command}', fg='green'))
        socket = container.exec_run(
            cmd=command,
            tty=True,
            stream=True,
        )

        for line in socket.output:
            click.echo(line, nl=False)

    def build(self, dockerfile, tag, rebuild):
        for chunk in self.client.api.build(path='.', dockerfile=dockerfile, tag=tag, nocache=rebuild, rm=True):
            for line in chunk.split(b'\r\n'):
                if not line:
                    continue
                data = json.loads(line)
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
