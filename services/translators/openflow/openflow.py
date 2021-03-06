from jinja2 import Environment, FileSystemLoader
from netaddr import IPAddress, IPNetwork
from yamlreader import yaml_load
from nameko.rpc import rpc, RpcProxy
import ast
from nameko.standalone.rpc import ClusterRpcProxy


CONFIG = {'AMQP_URI': "amqp://guest:guest@localhost:5672"}


def check_ip_network(ip, network):
    if ip == 'all':
        return False
    if IPAddress(ip) in IPNetwork(network):
        return True
    else:
        return False


def check_values(dict_intent):
    if dict_intent['intent_type'] == 'acl':
        parameters = ['from', 'to', 'rule', 'traffic', 'apply']
    elif dict_intent['intent_type'] == 'nat_1to1':
        parameters = ['from', 'to', 'protocol', 'apply']
    elif dict_intent['intent_type'] == 'traffic_shaping':
        parameters = ['from', 'to', 'with', 'traffic', 'apply']
    elif dict_intent['intent_type'] == 'dst_route':
        parameters = ['from', 'to', 'apply']
    elif dict_intent['intent_type'] == 'nat_nto1':
        parameters = ['from', 'to', 'apply']
    elif dict_intent['intent_type'] == 'url_filter':
        parameters = ['name', 'from', 'to', 'rule', 'apply']
    else:
        return "OPENFLOW TRANSLATOR: Intent type not supported"
    for parameter in parameters:
        if parameter not in dict_intent:
            return 'OPENFLOW TRANSLATOR: ' + parameter.upper() + ' parameter is missing'
    return True


def define_order(dict_intent):
    line = 0
    response = 0
    if dict_intent['intent_type'] == 'acl':
        file = 'rules/openflow_acls'
    elif dict_intent['intent_type'] == 'traffic_shaping':
        file = 'rules/openflow_ts'
    else:
        return "OPENFLOW MODULE: Order not found"
    with open(file) as archive:
        if dict_intent['apply'] == 'insert':
            if 'after' in dict_intent:
                if dict_intent['after'] == 'all-intents':
                    for line_num, l in enumerate(archive, 0):
                        line = line_num
                    response = 65535 - line
                    line = line + 1

                else:
                    for line_num, l in enumerate(archive, 0):
                        if "'name': '" + dict_intent['after'] + "'" in l:
                            line = line_num + 1
                            response = 65535 - line_num
            elif 'before' in dict_intent:
                if dict_intent['before'] == 'all-intents':
                    line = 1
                    response = 65535
                else:
                    for line_num, l in enumerate(archive, 0):
                        if "'name': '" + dict_intent['before'] + "'" in l:
                            line = line_num
                            response = 65535 - (line_num - 1)
        else:
            for line_num, l in enumerate(archive, 0):
                if "'name': '" + dict_intent['name'] + "'" in l:
                    line = line_num
                    response = 65535 - line_num
    archive.close()
    if line != 0:
        archive = open(file)
        lines = archive.readlines()
        archive.close()
        dict_intent['order'] = response
        if dict_intent['apply'] == 'insert':
            lines.insert(line, str(dict_intent) + "\n")
            if dict_intent['intent_type'] == 'traffic_shaping':
                lines.insert(line + 1, str(dict_intent) + "\n")
        else:
            lines.pop(line)
            if dict_intent['intent_type'] == 'traffic_shaping':
                lines.pop(line - 1)
        archive = open(file, 'w')
        archive.writelines(lines)
        archive.close()

    return response


def process_acl(dict_intent):
    # loading YAML with openflow settings
    config = yaml_load('openflow_config.yml')
    dict_intent['hostname'] = config['hostname']
    dict_intent['args'] = ''
    # from/to
    if 'from_mask' in dict_intent:
        dict_intent['from'] = dict_intent['from'] + '/' + dict_intent['from_mask']
    if 'to_mask' in dict_intent:
        dict_intent['to'] = dict_intent['to'] + '/' + dict_intent['to_mask']
    if dict_intent['from'] != 'all':
        dict_intent['args'] = dict_intent['args'] + 'nw_src=' + dict_intent['from'] + ','
    else:
        dict_intent['args'] = dict_intent['args'] + 'nw_src=0.0.0.0/0.0.0.0,'
    if dict_intent['to'] != 'all':
        dict_intent['args'] = dict_intent['args'] + 'nw_dst=' + dict_intent['to'] + ','
    else:
        dict_intent['args'] = dict_intent['args'] + 'nw_dst=0.0.0.0/0.0.0.0,'

    # translate protocol/port
    if dict_intent['traffic'] == 'icmp':
        dict_intent['args'] = dict_intent['args'] + 'nw_proto=1,icmp_type=8,'
    elif dict_intent['traffic'] != 'all':
        protocol, port = dict_intent['traffic'].split('/')
        dict_intent['traffic'] = protocol
        dict_intent['traffic_port'] = 'eq ' + port
        if protocol == 'tcp':
            dict_intent['args'] = dict_intent['args'] + 'nw_proto=6,tcp_dst=' + port + ','
        elif protocol == 'udp':
            dict_intent['args'] = dict_intent['args'] + 'nw_proto=17,udp_dst=' + port + ','

    if dict_intent['rule'] == 'block':
        dict_intent['rule'] = 'drop'
    else:
        dict_intent['rule'] = 'normal'

    order = define_order(dict_intent)
    if order != 0:
        dict_intent['order'] = order
    else:
        return 'OPENFLOW TRANSLATOR - ERROR ORDER: It was not possible to determine the order by name in order parameter'

    file_loader = FileSystemLoader('.')
    env = Environment(loader=file_loader)
    template = env.get_template('openflow_template.j2')
    response = template.render(dict_intent)
    output = 'ovs-ofctl del-flows ' + dict_intent['hostname'] + '\n'
    output = output + response + '\n'
    lines = ['# log acl rules \n']
    file = 'rules/openflow_acls'
    with open(file) as archive:
        for line in archive:
            if '#' not in line[0:5] and line[0:1] != "\n":
                dict_rule = ast.literal_eval(line)
                if int(dict_rule['order']) > int(dict_intent['order']):
                    tmp = template.render(dict_rule)
                    output = output + tmp + '\n'
                    lines.append(str(dict_rule) + '\n')
                elif int(dict_rule['order']) <= int(dict_intent['order']):
                    if dict_rule['name'] == dict_intent['name']:
                        lines.append(str(dict_rule) + '\n')
                    else:
                        if dict_intent['apply'] == 'insert':
                            dict_rule['order'] = int(dict_rule['order']) - 1
                        else:
                            dict_rule['order'] = int(dict_rule['order']) + 1
                        tmp = template.render(dict_rule)
                        output = output + tmp + '\n'
                        lines.append(str(dict_rule) + '\n')
    archive.close()
    archive = open(file, 'w')
    archive.writelines(lines)
    archive.close()
    output = output + '\novs-ofctl add-flow ' + dict_intent['hostname'] + ' priority=0,action=normal'

    #with ClusterRpcProxy(CONFIG) as rpc_connect:
    #   rpc_connect.linux_connector.apply_config(config['ip_manage'], config['ssh_port'], config['username'], config['password'],
    #                                           config['device_type'], output, 'openflow')
    return response


def process_nat11(dict_intent):
    # loading YAML file with firewall settings
    config = yaml_load('openflow_config.yml')
    dict_intent['hostname'] = config['hostname']
    # loading and render template jinja2
    file_loader = FileSystemLoader('.')
    env = Environment(loader=file_loader)
    template = env.get_template('openflow_template.j2')
    output = template.render(dict_intent)
    #with ClusterRpcProxy(CONFIG) as rpc_connect:
    #   rpc_connect.linux_connector.apply_config(config['ip_manage'], config['ssh_port'], config['username'], config['password'],
    #                                           config['device_type'], output, 'openflow')
    return output


def process_traffic_shaping(dict_intent):
    # converting throughput and rate
    dict_intent['with'] = dict_intent['with'] * 1000
    dict_intent['burst'] = int(dict_intent['with'] / 10)
    # loading YAML file with firewall settings
    config = yaml_load('openflow_config.yml')
    dict_intent['hostname'] = config['hostname']
    # loading and render template jinja2
    file_loader = FileSystemLoader('.')
    env = Environment(loader=file_loader)
    template = env.get_template('openflow_template.j2')
    output = template.render(dict_intent)
    #with ClusterRpcProxy(CONFIG) as rpc_connect:
    #    rpc_connect.linux_connector.apply_config(config['ip_manage'], config['ssh_port'], config['username'],
    #                                             config['password'],
    #                                             config['device_type'], output, 'openflow')
    return output


def process_dst_route(dict_intent):
    return 'OPENFLOW TRANSLATOR: Route is not yet supported'


def process_natn1(dict_intent):
    return 'OPENFLOW TRANSLATOR: NAT Nto1 is not yet supported'


def process_url_filter(dict_intent):
    return 'OPENFLOW TRANSLATOR: URL Filter is not yet supported'


class OpenflowService:
    """
        Openflow Service
        Microservice that translates the information sent by the api to commands applicable in Openflow devices
        Receive: this function receives a python dictionary, with at least the following information for each processing
        Return:
            - The microservice activates the application module via ssh and returns the result. If any incorrect
            information in the dictionary, the error message is returned
        Translations for NAT1toN and Route have not yet been implemented
        """
    name = "openflow_translator"
    zipcode_rpc = RpcProxy('openflow_service_translator')

    @rpc
    def translate_intent(self, dict_intent):
        if 'intent_type' in dict_intent:
            output = check_values(dict_intent)
            if output is True:
                if dict_intent['intent_type'] == 'acl':
                    return process_acl(dict_intent)
                elif dict_intent['intent_type'] == 'nat_1to1':
                    return process_nat11(dict_intent)
                elif dict_intent['intent_type'] == 'traffic_shaping':
                    return process_traffic_shaping(dict_intent)
                elif dict_intent['intent_type'] == 'dst_route':
                    return process_dst_route(dict_intent)
                elif dict_intent['intent_type'] == 'nat_nto1':
                    return process_natn1(dict_intent)
                elif dict_intent['intent_type'] == 'url_filter':
                    return process_url_filter(dict_intent)
            else:
                return output
        else:
            return 'OPENFLOW TRANSLATOR: the key "intent_type" is unavailable in the dictionary'

