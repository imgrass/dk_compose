from dk_compose import DockerDeploy


class Const(DockerDeploy):
    Con_dir_workspace = '/home/eouylei/imgrass/tools/docker_compose/workspace'
    #Con_dir_src = '/home/eouylei/imgrass/source-code/ecs-mos'

    ## network
    # bridge: stk_mgmt
    Con_ntw_mgmt = {
        'name'      : 'stk_mgmt',
        'subnet'    : '10.1.0.0/24',
        'gateway'   : '10.1.0.254',
        'container' : {
            'example1'  : '10.1.0.111',
            'example2'  : '10.1.0.112',
        },
    }

    # /etc/hosts
    Con_hosts = '''
        127.0.0.1       localhost
        ::1     localhost ip6-localhost ip6-loopback
        fe00::0 ip6-localnet
        ff00::0 ip6-mcastprefix
        ff02::1 ip6-allnodes
        ff02::2 ip6-allrouters

        10.1.0.111       example1
        10.1.0.112       example2
    '''


class CfgExample1(object):
    '''
    env = [
        'PYTHONPATH=/opt/keystone',
    ]
    '''
    env = []
    volumes = {
        # ==> directory ...
        '%s' % Const.Con_dir_workspace: {
            'bind': '/home',
            'mode': 'rw',
        },

        # =-=-> file ...
        '%s/etc/hosts' % Const.Con_dir_workspace: {
            'bind': '/etc/hosts',
            'mode': 'rw',
        },
    }

    config = {
        'hostname'  : 'example1',
        'image'     : 'stk:latest',
        'name'      : 'example1',

        'env'       : env,
        'volumes'   : volumes,
    }

    exec_cmdlst = [
        {
            'cmd':'hostname',
            #'workdir':'/root'
        },
    ]


class CfgExample2(object):
    volumes = {
        # ==> directory ...
        '%s' % Const.Con_dir_workspace: {
            'bind': '/home',
            'mode': 'rw',
        },

        # =-=-> file ...
        '%s/etc/hosts' % Const.Con_dir_workspace: {
            'bind': '/etc/hosts',
            'mode': 'rw',
        },
    }

    config = {
        'hostname'  : 'example2',
        'image'     : 'stk:latest',
        'name'      : 'example2',

        'volumes'   : volumes,
    }

    exec_cmdlst = [
        {
            'cmd':'hostname',
        },
    ]


if __name__ == '__main__':
    hdr = Const()
    hdr.init_network()

    hdr.create_dk_container(CfgExample1)
    hdr.run_dk_cmd(CfgExample1)

    hdr.create_dk_container(CfgExample2)
    hdr.run_dk_cmd(CfgExample2)
