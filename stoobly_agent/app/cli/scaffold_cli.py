import click
import errno
import os
import pdb
import sys

from typing import List

from stoobly_agent.app.cli.helpers.certificate_authority import CertificateAuthority
from stoobly_agent.app.cli.helpers.shell import exec_stream
from stoobly_agent.app.cli.scaffold.app import App
from stoobly_agent.app.cli.scaffold.app_create_command import AppCreateCommand
from stoobly_agent.app.cli.scaffold.constants import (
  DOCKER_NAMESPACE, WORKFLOW_CONTAINER_PROXY, WORKFLOW_MOCK_TYPE, WORKFLOW_RECORD_TYPE, WORKFLOW_TEST_TYPE
)
from stoobly_agent.app.cli.scaffold.docker.service.set_gateway_ports import set_gateway_ports
from stoobly_agent.app.cli.scaffold.docker.workflow.decorators_factory import get_workflow_decorators
from stoobly_agent.app.cli.scaffold.hosts_file_manager import HostsFileManager
from stoobly_agent.app.cli.scaffold.service import Service
from stoobly_agent.app.cli.scaffold.service_config import ServiceConfig
from stoobly_agent.app.cli.scaffold.service_create_command import ServiceCreateCommand
from stoobly_agent.app.cli.scaffold.service_delete_command import ServiceDeleteCommand
from stoobly_agent.app.cli.scaffold.service_workflow_validate_command import ServiceWorkflowValidateCommand
from stoobly_agent.app.cli.scaffold.templates.constants import CORE_SERVICES
from stoobly_agent.app.cli.scaffold.validate_exceptions import ScaffoldValidateException
from stoobly_agent.app.cli.scaffold.workflow import Workflow
from stoobly_agent.app.cli.scaffold.workflow_create_command import WorkflowCreateCommand
from stoobly_agent.app.cli.scaffold.workflow_copy_command import WorkflowCopyCommand
from stoobly_agent.app.cli.scaffold.workflow_log_command import WorkflowLogCommand
from stoobly_agent.app.cli.scaffold.workflow_run_command import WorkflowRunCommand
from stoobly_agent.app.cli.scaffold.workflow_validate_command import WorkflowValidateCommand
from stoobly_agent.config.constants import env_vars
from stoobly_agent.config.data_dir import DataDir
from stoobly_agent.lib.logger import bcolors, DEBUG, ERROR, INFO, Logger, WARNING

LOG_ID = 'Scaffold'

@click.group(
    epilog="Run 'stoobly-agent project COMMAND --help' for more information on a command.",
    help="Manage scaffold"
)
@click.pass_context
def scaffold(ctx):
    pass

@click.group(
  epilog="Run 'stoobly-agent request response COMMAND --help' for more information on a command.",
  help="Manage app scaffold"
)
@click.pass_context
def app(ctx):
    pass

@click.group(
  epilog="Run 'stoobly-agent request response COMMAND --help' for more information on a command.",
  help="Manage service scaffold"
)
@click.pass_context
def service(ctx):
    pass

@app.command(
  help="Scaffold application"
)
@click.option('--app-dir-path', default=os.getcwd(), help='Path to create the app scaffold.')
@click.option('--force', is_flag=True, help='Overwrite maintained scaffolded app files.')
@click.argument('app_name')
def create(**kwargs):
  __validate_app_dir(kwargs['app_dir_path'])

  app = App(kwargs['app_dir_path'], DOCKER_NAMESPACE)

  if kwargs['force'] or not os.path.exists(app.namespace_path):
    __app_build(app, **kwargs)
  else:
    print(f"{kwargs['app_dir_path']} already exists, use option '--force' to continue ")

@app.command(
  help="Scaffold app service certs"
)
@click.option('--app-dir-path', default=os.getcwd(), help='Path to application directory.')
@click.option('--ca-certs-dir-path', default=DataDir.instance().mitmproxy_conf_dir_path, help='Path to ca certs directory used to sign SSL certs. Defaults to ~/.mitmproxy')
@click.option('--certs-dir-path', help='Path to certs directory. Defaults to the certs dir of the context.')
@click.option('--context-dir-path', default=DataDir.instance().context_dir_path, help='Path to Stoobly data directory.')
@click.option('--service', multiple=True, help='Select which services to run. Defaults to all.')
def mkcert(**kwargs):
  app = App(kwargs['app_dir_path'], DOCKER_NAMESPACE, ca_certs_dir_path=kwargs['ca_certs_dir_path'])

  if kwargs['certs_dir_path']:
    app.certs_dir_path = kwargs['certs_dir_path']

  if kwargs['context_dir_path']:
    app.context_dir_path = kwargs['context_dir_path']

  if not app.exists:
    print(f"Error: {app.dir_path} does not exist", file=sys.stderr)
    sys.exit(1)

  services = __get_services(app.services, service=kwargs['service'])

  for service_name in services:
    service = Service(service_name, app)
    service_config = ServiceConfig(service.dir_path)

    if service_config.scheme != 'https':
      continue

    hostname = service_config.hostname
    
    if not hostname:
      continue

    ca = CertificateAuthority(app.ca_certs_dir_path)
    if not ca.signed(hostname, app.certs_dir_path):
      Logger.instance(LOG_ID).info(f"Creating cert for {hostname}")
      ca.sign(hostname, app.certs_dir_path)

@service.command(
  help="Scaffold a service",
)
@click.option('--app-dir-path', default=os.getcwd(), help='Path to application directory.')
@click.option('--detached', is_flag=True)
@click.option('--env', multiple=True, help='Specify an environment variable.')
@click.option('--force', is_flag=True, help='Overwrite maintained scaffolded service files.')
@click.option('--hostname')
@click.option('--port')
@click.option('--priority', default='5.0', help='Determines the service run order.')
@click.option('--proxy-mode', help='''
  Proxy mode can be "regular", "transparent", "socks5",
  "reverse:SPEC", or "upstream:SPEC". For reverse and
  upstream proxy modes, SPEC is host specification in
  the form of "http[s]://host[:port]".
''')
@click.option('--scheme', type=click.Choice(['http', 'https']))
@click.option('--workflow', multiple=True, type=click.Choice([WORKFLOW_MOCK_TYPE, WORKFLOW_RECORD_TYPE, WORKFLOW_TEST_TYPE]), help='Include pre-defined workflows.')
@click.argument('service_name')
def create(**kwargs):
  __validate_app_dir(kwargs['app_dir_path'])

  app = App(kwargs['app_dir_path'], DOCKER_NAMESPACE)

  service = Service(kwargs['service_name'], app)
  if kwargs['force'] or not os.path.exists(service.dir_path):
    __scaffold_build(app, **kwargs)
  else:
    print(f"{service.dir_path} already exists, use option '--force' to continue")

@service.command(
  help="Delete a service",
)
@click.option('--app-dir-path', default=os.getcwd(), help='Path to application directory.')
@click.argument('service_name')
def delete(**kwargs):
  __validate_app_dir(kwargs['app_dir_path'])

  app = App(kwargs['app_dir_path'], DOCKER_NAMESPACE)
  service = Service(kwargs['service_name'], app)

  if not os.path.exists(service.dir_path):
    print(f"Service does not exist, so not deleting")
  else:
    print(f"Deleting service: {service.service_name}")
    __scaffold_delete(app, **kwargs)
    print(f"Successfully deleted service: {service.service_name}")

@service.command(
  help="Update a service config"
)
@click.option('--app-dir-path', default=os.getcwd(), help='Path to application directory.')
@click.option('--priority', help='Determines the service run order.')
@click.argument('service_name')
def update(**kwargs):
  __validate_app_dir(kwargs['app_dir_path'])

  app = App(kwargs['app_dir_path'], DOCKER_NAMESPACE)
  service = Service(kwargs['service_name'], app)

  __validate_service_dir(service.dir_path)

  service_config = ServiceConfig(service.dir_path)

  if kwargs['priority']:
    service_config.priority = kwargs['priority']

  service_config.write()

@click.group(
  epilog="Run 'stoobly-agent request response COMMAND --help' for more information on a command.",
  help="Manage service scaffold"
)
@click.pass_context
def workflow(ctx):
    pass

@workflow.command(
  help="Create workflow for service(s)"
)
@click.option('--app-dir-path', default=os.getcwd(), help='Path to application directory.')
@click.option('--env', multiple=True, help='Specify an environment variable.')
@click.option('--force', is_flag=True, help='Overwrite maintained scaffolded workflow files.')
@click.option('--service', multiple=True, help='Specify the service(s) to create the workflow for.')
@click.option('--template', type=click.Choice([WORKFLOW_MOCK_TYPE, WORKFLOW_RECORD_TYPE, WORKFLOW_TEST_TYPE]), help='Select which workflow to use as a template.')
@click.argument('workflow_name')
def create(**kwargs):
  __validate_app_dir(kwargs['app_dir_path'])

  app = App(kwargs['app_dir_path'], DOCKER_NAMESPACE)

  for service_name in kwargs['service']:
    config = { **kwargs }
    del config['service']
    config['service_name'] = service_name

    service = Service(service_name, app)
    __validate_service_dir(service.dir_path)

    workflow_dir_path = service.workflow_dir_path(kwargs['workflow_name'])
    if kwargs['force'] or not os.path.exists(workflow_dir_path):
      __workflow_build(app, **config)
    else:
      print(f"{workflow_dir_path} already exists, use option '--force' to continue")

@workflow.command(
  help="Copy a workflow for service(s)",
)
@click.option('--app-dir-path', default=os.getcwd(), help='Path to application directory.')
@click.option('--service', multiple=True, help='Specify service(s) to add the workflow to.')
@click.argument('workflow_name')
@click.argument('destination_workflow_name')
def copy(**kwargs):
  app = App(kwargs['app_dir_path'], DOCKER_NAMESPACE)

  for service_name in kwargs['service']:
    config = { **kwargs }
    del config['service']
    config['service_name'] = service_name
      
    command = WorkflowCopyCommand(app, **config)

    if not command.app_dir_exists:
      print(f"Error: {command.app_dir_path} does not exist", file=sys.stderr)
      sys.exit(1)

    command.copy(kwargs['destination_workflow_name'])

@workflow.command()
@click.option('--app-dir-path', default=os.getcwd(), help='Path to application directory.')
@click.option('--context-dir-path', default=DataDir.instance().context_dir_path, help='Path to Stoobly data directory.')
@click.option('--dry-run', default=False, is_flag=True)
@click.option('--log-level', default=INFO, type=click.Choice([DEBUG, INFO, WARNING, ERROR]), help='''
    Log levels can be "debug", "info", "warning", or "error"
''')
@click.option('--namespace', help='Workflow namespace.')
@click.option('--rmi', is_flag=True, help='Remove images used by containers.')
@click.option('--service', multiple=True, help='Select which services to log. Defaults to all.')
@click.argument('workflow_name')
def stop(**kwargs):  
  cwd = os.getcwd()

  if not os.getenv(env_vars.LOG_LEVEL):
    os.environ[env_vars.LOG_LEVEL] = kwargs['log_level']

  app = App(kwargs['app_dir_path'], DOCKER_NAMESPACE, skip_validate_path=True)

  if kwargs['context_dir_path']:
    app.context_dir_path = kwargs['context_dir_path']

  if not app.exists:
    print(f"Error: {app.dir_path} does not exist", file=sys.stderr)
    sys.exit(1)

  workflow = Workflow(kwargs['workflow_name'], app)
  services = __get_services(workflow.services, service=kwargs['service'])

  commands: List[WorkflowRunCommand] = []
  for service in services:
    config = { **kwargs }
    config['service_name'] = service
    command = WorkflowRunCommand(app, **config)
    command.current_working_dir = cwd
    commands.append(command)

  commands = sorted(commands, key=lambda command: command.service_config.priority)

  for command in commands:
    __print_header(f"SERVICE {command.service_name}")

    exec_command = command.down(namespace=kwargs['namespace'], rmi=kwargs['rmi'])
    if not exec_command:
      continue

    if not kwargs['dry_run']:
      exec_stream(exec_command)
    else:
      print(exec_command)

@workflow.command()
@click.option('--app-dir-path', default=os.getcwd(), help='Path to application directory.')
@click.option(
  '--container', multiple=True, help=f"Select which containers to log. Defaults to '{WORKFLOW_CONTAINER_PROXY}'"
)
@click.option('--dry-run', default=False, is_flag=True, help='If set, prints commands.')
@click.option('--follow', is_flag=True, help='Follow last container log output.')
@click.option('--namespace', help='Workflow namespace.')
@click.option('--service', multiple=True, help='Select which services to log. Defaults to all.')
@click.argument('workflow_name')
def logs(**kwargs):
  if len(kwargs['container']) == 0:
    kwargs['container'] = [WORKFLOW_CONTAINER_PROXY]

  app = App(kwargs['app_dir_path'], DOCKER_NAMESPACE)

  if not app.exists:
    print(f"Error: {app.dir_path} does not exist", file=sys.stderr)
    sys.exit(1)

  workflow = Workflow(kwargs['workflow_name'], app)
  services = __get_services(workflow.services, service=kwargs['service'], without_core=True)

  commands: List[WorkflowLogCommand] = []
  for service in services:
    if len(kwargs['service']) == 0:
      # If no filter is specified, ignore CORE_SERVICES
      if service in CORE_SERVICES:
        continue
    else:
      # If a filter is specified, ignore all other services
      if service not in kwargs['service']:
        continue

    config = { **kwargs }
    config['service_name'] = service 
    command = WorkflowLogCommand(app, **config)
    commands.append(command)

  commands = sorted(commands, key=lambda command: command.service_config.priority)

  for index, command in enumerate(commands):
    __print_header(f"SERVICE {command.service_name}")

    follow = kwargs['follow'] and index == len(commands) - 1
    shell_commands = command.build(
      containers=kwargs['container'], follow=follow, namespace=kwargs['namespace']
    )

    for shell_command in shell_commands:
      print(shell_command)

      if not kwargs['dry_run']:
        exec_stream(shell_command)
 
@workflow.command()
@click.option('--app-dir-path', default=os.getcwd(), help='Path to application directory.')
@click.option('--ca-certs-dir-path', default=DataDir.instance().mitmproxy_conf_dir_path, help='Path to ca certs directory used to sign SSL certs. Defaults to ~/.mitmproxy')
@click.option('--certs-dir-path', help='Path to certs directory. Defaults to the certs dir of the context.')
@click.option('--context-dir-path', default=DataDir.instance().context_dir_path, help='Path to Stoobly data directory.')
@click.option('--detached', is_flag=True, help='If set, will not run the highest priority service in the foreground.')
@click.option('--dry-run', default=False, is_flag=True, help='If set, prints commands.')
@click.option('--extra-compose-path', help='Path to extra compose configuration files.')
@click.option('--log-level', default=INFO, type=click.Choice([DEBUG, INFO, WARNING, ERROR]), help='''
    Log levels can be "debug", "info", "warning", or "error"
''')
@click.option('--namespace', help='Workflow namespace.')
@click.option('--network', help='Workflow network namespace.')
@click.option('--no-cache', is_flag=True, help='Do not use cache when building images.')
@click.option('--service', multiple=True, help='Select which services to run. Defaults to all.')
@click.option('--verbose', is_flag=True)
@click.argument('workflow_name')
def run(**kwargs):
  cwd = os.getcwd()

  # Create the certs_dir_path if it doesn't exist
  DataDir.instance().certs_dir_path

  if not os.getenv(env_vars.LOG_LEVEL):
    os.environ[env_vars.LOG_LEVEL] = kwargs['log_level']

  app = App(
    kwargs['app_dir_path'], DOCKER_NAMESPACE, 
    ca_certs_dir_path=kwargs['ca_certs_dir_path'], skip_validate_path=kwargs['dry_run']
  )

  if kwargs['certs_dir_path']:
    app.certs_dir_path = kwargs['certs_dir_path']

  if kwargs['context_dir_path']:
    app.context_dir_path = kwargs['context_dir_path']

  if not app.exists:
    print(f"Error: {app.dir_path} does not exist", file=sys.stderr)
    sys.exit(1)

  workflow = Workflow(kwargs['workflow_name'], app)
  services = __get_services(workflow.services, service=kwargs['service'])

  # Gateway ports are dynamically set depending on the workflow run
  set_gateway_ports(workflow.service_paths_from_services(services))

  commands: List[WorkflowRunCommand] = []
  for service in services:
    config = { **kwargs }
    config['service_name'] = service
    command = WorkflowRunCommand(app, **config)
    command.current_working_dir = cwd
    commands.append(command)

  # Before services can be started, their network needs to be created
  if len(commands) > 0:
    command = commands[0]
    create_network_command = command.create_network()

    if not kwargs['dry_run']:
      command.write_nameservers()

      exec_stream(create_network_command)
    else:
      print(create_network_command)

  commands = sorted(commands, key=lambda command: command.service_config.priority)
  for index, command in enumerate(commands):
    __print_header(f"SERVICE {command.service_name}")

    # By default, the entrypoint service should be last
    # However, this can change if the user has configured a service's priority to be higher
    attached = not kwargs['detached'] and index == len(commands) - 1
    exec_command = command.up(
      attached=attached, namespace=kwargs['namespace'], no_cache=kwargs['no_cache'], verbose=kwargs['verbose']
    )
    if not exec_command:
      continue

    if not kwargs['dry_run']:
      exec_stream(exec_command)
    else:
      print(exec_command)

@workflow.command(
  help="Validate a scaffold workflow"
)
@click.option('--app-dir-path', default=os.getcwd(), help='Path to validate the app scaffold.')
@click.argument('workflow_name')
def validate(**kwargs):
  app = App(kwargs['app_dir_path'], DOCKER_NAMESPACE)
  workflow = Workflow(kwargs['workflow_name'], app)
  
  config = { **kwargs }
  config['service_name'] = 'build'

  try:
    command = WorkflowValidateCommand(app, **config)
    command.validate()
  except ScaffoldValidateException as sve:
    print(f"\nFatal Scaffold Validation Exception: {sve}", file=sys.stderr)
    sys.exit(1)

  try:
    for service in workflow.services_ran:
      if service not in CORE_SERVICES:
        config['service_name'] = service
        command = ServiceWorkflowValidateCommand(app, **config)
        command.validate()
  except ScaffoldValidateException as sve:
    print(f"\nFatal Scaffold Validation Exception: {sve}", file=sys.stderr)
    sys.exit(1)

@click.group(
  epilog="Run 'stoobly-agent scaffold hostname COMMAND --help' for more information on a command.",
  help="Manage scaffold service hostnames"
)
@click.pass_context
def hostname(ctx):
    pass

@hostname.command(
  help="Update the system hosts file for all scaffold service hostnames"
)
@click.option('--app-dir-path', default=os.getcwd(), help='Path to validate the app scaffold.')
def install(**kwargs):
  app = App(kwargs['app_dir_path'], DOCKER_NAMESPACE)
  services = app.services
  services = list(filter(lambda service: service not in CORE_SERVICES, services))

  hostnames = []
  for service_name in services:
    service = Service(service_name, app)
    service_config = ServiceConfig(service.dir_path)
    hostnames.append(service_config.hostname)

  hosts_file_manager = HostsFileManager()

  try:
    hosts_file_manager.install_hostnames(hostnames)
  except PermissionError:
    print("Permission denied. Please run this command with sudo.")

@hostname.command(
  help="Delete from the system hosts file all scaffold service hostnames"
)
@click.option('--app-dir-path', default=os.getcwd(), help='Path to validate the app scaffold.')
def uninstall(**kwargs):
  app = App(kwargs['app_dir_path'], DOCKER_NAMESPACE)
  services = app.services
  services = list(filter(lambda service: service not in CORE_SERVICES, services))

  hostnames = []
  for service_name in services:
    service = Service(service_name, app)
    service_config = ServiceConfig(service.dir_path)
    hostnames.append(service_config.hostname)

  hosts_file_manager = HostsFileManager()

  try:
    hosts_file_manager.uninstall_hostnames(hostnames)
  except OSError as e:
    if e.errno == errno.EACCES or e.errno == errno.EPERM:
      print("Permission denied. Please run this command with sudo.")
    else:
      print(f"An unexpected error occurred: {e}")


scaffold.add_command(app)
scaffold.add_command(service)
scaffold.add_command(workflow)
scaffold.add_command(hostname)

def __get_services(services: List[str], **kwargs):
  # Log services that don't exist
  missing_services = [service for service in kwargs['service'] if service not in services]
  if missing_services:
    Logger.instance(LOG_ID).warn(f"Service(s) {','.join(missing_services)} are not found")

  if kwargs['service']:
    # If service is specified, run only those services
    services = list(kwargs['service'])

    if not kwargs.get('without_core'):
      services += CORE_SERVICES
  else:
    # If set, filter out core services
    if kwargs.get('without_core'):
      services = list(filter(lambda service: service not in CORE_SERVICES, services))
    
  return list(set(services))

def __print_header(text: str):
  Logger.instance(LOG_ID).info(f"{bcolors.OKBLUE}{text}{bcolors.ENDC}")

def __app_build(app, **kwargs):
  AppCreateCommand(app, **kwargs).build()

def __scaffold_build(app, **kwargs):
  command = ServiceCreateCommand(app, **kwargs)

  command.build()

def __scaffold_delete(app, **kwargs):
  command = ServiceDeleteCommand(app, **kwargs)

  command.delete()

def __validate_app_dir(app_dir_path):
  if not os.path.exists(app_dir_path):
    print(f"Error: {app_dir_path} does not exist", file=sys.stderr)
    sys.exit(1)

def __validate_service_dir(service_dir_path):
  if not os.path.exists(service_dir_path):
    print(f"Error: {service_dir_path} does not exist, please scaffold this service", file=sys.stderr)
    sys.exit(1)

def __workflow_build(app, **kwargs):
  command = WorkflowCreateCommand(app, **kwargs)

  service_config = command.service_config
  workflow_decorators = get_workflow_decorators(kwargs['template'], service_config)
  command.build(
    headless=kwargs['headless'],
    template=kwargs['template'],
    workflow_decorators=workflow_decorators
  )
