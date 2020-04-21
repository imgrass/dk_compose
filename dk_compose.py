'''
Description:
    This module is used to comfort to deploy docker cluster.

Usage:
    To use this module, servral config classes should be prepared, let's assume to
    build two containers named <example1> and <example2>.
    *) class
        1> @class Const(DockerDeploy)   # define global configuration
            *<string>: Con_dir_workspace
            *<string>: Con_hosts
            *<dict>  : Con_ntw_[bridge name]

        2> @class CfgExample1(object)   # define local configuration
        3> @class CfgExample2(object)
            *<dict>  : config ->
                *<string>: hostname
                *<string>: image
                *<string>: name
                *<list>  : env
                *<dict>  : volumes

            *<list>  : exec_cmdlst ->
                *<dict> ->
                    *<string>: cmd
                    *<string>: workdir


    Note that the class <Const> must inherit class <DockerDeploy>. It would
    do some initialization actions and set global parameters. Then class@1
    and class@2 would provide detailed configuration params to build
    corresponding container.

    The class DockerDeploy provides some functions shown below:
    *) function
        1> @init_network    # init global docker network defined by Const
        2> @create_dk_container    # create a container and configured by
                                      self-defined class like class@1,2
        3> @run_dk_cmd     # run commands defined in self-defined class in
                              corresponding container

Example:
    Ref to <./test/ut_example_config.py>
    Ref link:
        [https://docker-py.readthedocs.io/en/stable/client.html]
'''
#!/usr/bin/env python
import docker
import os
import sys
from traceback import print_exc


class ExceptionConstArgvNotSet(Exception):
    def __init__(self, arg_name):
        self.arg_name = arg_name

    def __str__(self):
        return 'Constant argument named <%s> was not set' % self.arg_name


class DockerDeployBase(object):
    '''
    Provide the base implementation for all Openstack mouldes.
    '''
    dk_client = docker.from_env()

    def create_network(self, **kwargs):
        name    = kwargs['name']
        subnet  = kwargs['subnet']
        gateway = kwargs['gateway']

        driver  = kwargs.get('driver', 'bridge')

        print('+ Create network %s with <subnet:%s> <gateway:%s>' %
              (name, subnet, gateway))
        try:
            network = self.dk_client.networks.get(name)
            ipam_config = network.attrs.get('IPAM').get('Config')
            for ipam in ipam_config:
                if ipam.get('Subnet') == subnet and \
                   ipam.get('Gateway') == gateway:
                    print('  Network already existed')
                    return
            network.remove()
            print('  ==> remove existed network %s' % name)
        except docker.errors.NotFound:
            pass

        ipam_pool = docker.types.IPAMPool(subnet=subnet, gateway=gateway)
        ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])
        return self.dk_client.networks.create(name, driver=driver,
                                              ipam=ipam_config)

    def create_container(self, **kwargs):
        hostname = kwargs['hostname']
        image    = kwargs['image']
        name     = kwargs['name']

        cap_add  = kwargs.get('cap_add', 'SYS_ADMIN')
        command  = kwargs.get('command', '/sbin/init')
        env      = kwargs.get('env', None)
        volumes  = kwargs.get('volumes', None)

        print('+ Create container %s with <image:%s> <command:%s>' %
              (name, image, command))
        try:
            self.dk_client.containers.get(name).remove(force=True)
            print('+ ==> remove existed container %s' % name)
        except docker.errors.NotFound:
            pass

        return self.dk_client.containers.run(
            image, command, cap_add=cap_add, detach=True, environment=env,
            hostname=hostname, name=name, volumes=volumes)

    def exec_run(self, container, command, workdir=None):
        exit, output = container.exec_run(command, workdir=workdir)
        print('..run <%s> in container %s with exit code %d' %
              (command, container.name, exit))
        if exit is 0:
            print('<DEBUG>: output is\n%s' % output)
        else:
            print('<FAILED>: output is\n%s' % output)

        return exit


class DockerDeploy(DockerDeployBase):
    '''
    This class must be iherited by a customer class that provides all sorts of
    constant global argvs needed.
    '''
    def __init__(self):
        super(DockerDeploy, self).__init__()

        self.customer_ntw_devs = []
        self.hdr_container = None

        self._validate_config_argv()
        self._init_global_env()

    def _init_global_env(self):
        #1> check if needed directories and files are provided or not.
        if not os.path.isdir(self.Con_dir_workspace):
            os.mkdir(self.Con_dir_workspace, 0755);

        #2> write hosts
        try:
            os.mkdir('%s/etc' % self.Con_dir_workspace, 0755)
        except OSError:
            pass
        fp_hosts = open('%s/etc/hosts' % self.Con_dir_workspace, 'w')
        for line in self.Con_hosts.split('\n'):
            if len(line) > 0:
                fp_hosts.write(line.strip(' ')+'\n')
        fp_hosts.close()

    def _validate_config_argv(self):
        # This params should be provided by subclass
        mandatory_argv_const = [
                'Con_dir_workspace',
                'Con_hosts',
        ]
        for argv in mandatory_argv_const:
            if not hasattr(self, argv):
                raise ExceptionConstArgvNotSet(argv)

    def init_network(self):
        ## docker network
        # find all network device defined by customer
        self.customer_ntw_devs = [getattr(self, k) for k in dir(self) \
                if k[:8]=='Con_ntw_' and isinstance(getattr(self, k), dict)]   
        for ntw_dev in self.customer_ntw_devs:
            self.create_network(**ntw_dev)

    def _connect_network_with_config(self, hdr_container,
            is_strip_default_network=True):

        ntw_lst = [k for k in self.customer_ntw_devs if \
                hdr_container.name in k['container']]

        for ntw in ntw_lst:
            hdr_ntw = self.dk_client.networks.get(ntw['name'])
            if hdr_container in hdr_ntw.containers:
                print('  Network already connect')
                return
            ipv4_addr = ntw['container'][hdr_container.name]
            hdr_ntw.connect(hdr_container, ipv4_address=ipv4_addr)
            print('+ Connect network %s to %s with ipv4 addr %s' %
                  (hdr_ntw.name, hdr_container.name, ipv4_addr))

        # disconnect default bridge driver named 'bridge' which ip range is
        # 172.17.0.0/16
        if is_strip_default_network:
            print('+ Strip default bridge')
            self.dk_client.networks.get('bridge').disconnect(hdr_container)

    def create_dk_container(self, single_container_conf_cls):
        try:
            name = single_container_conf_cls.config['name']
        except AttributeError as e:
            print_exc()
            print('- Get container name failed due to %s' % e)
            print('-<Note>: it needs a class defining all needed params')
            sys.exit(1)

        print('+ Start to create <container:%s>' % name)
        self.hdr_container = self.create_container(
            **single_container_conf_cls.config)
        if not self.hdr_container:
            print('- Create container named %s failed' % name)
            sys.exit(1)
        print('... Successfully create container keystone with <id:%s>' %
              self.hdr_container.id)

        print('+ Start to connect network to container %s' % name)
        try:
            is_strip_default_network = single_container_conf_cls.\
                    is_strip_default_network
        except AttributeError:
            print_exc()
            is_strip_default_network = True
        self._connect_network_with_config(self.hdr_container,
                is_strip_default_network=is_strip_default_network)

    def run_dk_cmd(self, single_container_conf_cls):
        try:
            name = single_container_conf_cls.config['name']
        except AttributeError as e:
            print_exc()
            print('- Get container name failed due to %s' % e)
            print('-<Note>: it needs a class defining all needed params')
            sys.exit(1)

        # We want there is only one container handler in object at a certain
        # moment and execute its commands
        hdr_container = self.hdr_container or\
                       self.dk_client.containers.get(name)
        if hdr_container.name != name:
            print('- It excepted to run command in container %s, but current '
                  'container handler is %s' % (name, hdr_container.name))
            sys.exit(1)

        exec_cmdlst = single_container_conf_cls.exec_cmdlst or []
        for exec_cmd in exec_cmdlst:
            self.exec_run(hdr_container, exec_cmd['cmd'],
                    workdir=exec_cmd.get('workdir', None))
