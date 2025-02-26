import os
import pdb
import socket
import ssl
import time
from collections import Counter
from pathlib import Path

import requests
import yaml
from docker.models.containers import Container
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from stoobly_agent.app.cli.scaffold.constants import (
  FIXTURES_FOLDER_NAME,
  STOOBLY_DATA_DIR,
  STOOBLY_HOME_DIR,
  VIRTUAL_HOST_ENV,
  VIRTUAL_PORT_ENV,
  VIRTUAL_PROTO_ENV,
  WORKFLOW_RECORD_TYPE,
  WORKFLOW_TEST_TYPE,
)
from stoobly_agent.app.cli.scaffold.hosts_file_manager import HostsFileManager
from stoobly_agent.app.cli.scaffold.service_command import ServiceCommand
from stoobly_agent.app.cli.scaffold.service_docker_compose import ServiceDockerCompose
from stoobly_agent.app.cli.scaffold.validate_command import ValidateCommand
from stoobly_agent.app.cli.scaffold.validate_exceptions import ScaffoldValidateException
from stoobly_agent.config.data_dir import DATA_DIR_NAME

from .app import App


class ServiceWorkflowValidateCommand(ServiceCommand, ValidateCommand):
  def __init__(self, app: App, **kwargs):
    ServiceCommand.__init__(self, app, **kwargs)
    ValidateCommand.__init__(self)

    self.workflow_name = kwargs['workflow_name']
    self.hostname = self.service_config.hostname
    self.service_docker_compose = ServiceDockerCompose(app_dir_path=app.dir_path, target_workflow_name=self.workflow_name, service_name=self.service_name, hostname=self.hostname)

  @property
  def fixtures_dir_path(self):
    return os.path.join(self.workflow_path, FIXTURES_FOLDER_NAME)
  
  @property
  def workflow_path(self):
    return os.path.join(
      self.scaffold_dir_path,
      self.workflow_relative_path
    )
  @property
  def workflow_relative_path(self):
    return os.path.join(
      self.service_relative_path,
      self.workflow_name
    )

  def is_local(self):
    with open (self.service_docker_compose.docker_compose_path,'rb') as f:
      docker_compose_file_content = yaml.safe_load(f)
      if docker_compose_file_content and docker_compose_file_content.get('services'):
        return True

      # We can potentially check the port too someday

    return False

  def is_external(self):
    return not self.is_local()

  def hostname_reachable(self, hostname: str, port: int) -> bool:
    print(f"Validating connection to hostname: {hostname}, port: {port}")
    timeout = 1
    retries = 15
    delay = 0.100

    for attempt in range(retries):
      try:
        with socket.create_connection((hostname, port), timeout=timeout):
          return True
      except (socket.timeout, socket.error):
        if attempt < retries - 1:
          time.sleep(delay)

    raise ScaffoldValidateException(f"Connection failed to hostname: {hostname}, port: {port}")

  # Check if hostname is defined in hosts file
  def hostname_exists(self, hostname: str) -> bool:
    print(f"Validating hostname exists in hosts file for hostname: {hostname}")

    hosts_file_manager = HostsFileManager()
    host_mapping = hosts_file_manager.find_host(hostname)
    if host_mapping:
      print(f"Correct hosts mapping found for {hostname}")
      return True

    raise ScaffoldValidateException(f"Missing hosts mapping for {hostname}")
 
  def validate_hostname(self, hostname: str, port: int) -> None:
    print(f"Validating hostname: {hostname}")

    self.hostname_exists(hostname)

    self.hostname_reachable(hostname, port)

    # TODO: check logs of proxy. lifecycle hook for custom logging? Does mitmproxy support json logging?

  def validate_internal_hostname(self, url: str) -> None:
    print(f"Validating hostname inside Docker network, url: {url}")
    
    timeout_seconds = 1
    output = self.docker_client.containers.run(
      image='curlimages/curl:8.11.0',
      command=f"curl --max-time {timeout_seconds} {url} --verbose",
      network=self.app_config.network,
      stderr=True,
      remove=True,
    )

    # Note: 499 error could also mean success because it shows the proxy
    # connection is working, but we haven't recorded anything yet
    logs = output.decode('ascii')
    if ('200 OK' not in logs) and ('499' not in logs):
      raise ScaffoldValidateException(f"Error reaching {url} from inside Docker network")

  # Check fixtures folder mounted into container
  def validate_fixtures_folder(self, container: Container):
    
    if self.workflow_name == WORKFLOW_RECORD_TYPE:
      print(f"Skipping validating fixtures folder in workflow: {self.workflow_name}, container: {container.name}")
      return

    print(f"Validating fixtures folder in container: {container.name}")

    data_dir_mounted = False
    volume_mounts = container.attrs['Mounts']

    for volume_mount in volume_mounts:
      if volume_mount['Destination'] == STOOBLY_DATA_DIR:
        data_dir_mounted = True
        break
    if not data_dir_mounted:
      raise ScaffoldValidateException(f"Data directory is not mounted for: {container.name}")

    # Only the running proxy containers will be checkable
    if container.status == 'exited':
      print(f"Skipping validating fixtures folder contents because container is exited: {container.name}")
      return

    # Check contents of fixtures folder to confirm it's shared
    fixtures_folder_path = f"{STOOBLY_HOME_DIR}/{self.workflow_name}/{FIXTURES_FOLDER_NAME}"
    exec_result = container.exec_run(f"ls -A {fixtures_folder_path}")
    output = exec_result.output

    fixtures_folder_contents_container = output.decode('ascii').split('\n')
    if fixtures_folder_contents_container[-1] == '':
      fixtures_folder_contents_container.pop()
    fixtures_folder_contents_scaffold = os.listdir(self.fixtures_dir_path)

    if Counter(fixtures_folder_contents_container) != Counter(fixtures_folder_contents_scaffold):
      raise ScaffoldValidateException(f"Fixtures was not mounted properly, expected {self.fixtures_dir_path} to exist in container path {fixtures_folder_path}")

  # Note: might not need this if the hostname is reachable and working
  def proxy_environment_variables_exist(self, container: Container) -> None:
    environment_variables = container.attrs['Config']['Env']
    virtual_host_exists = False
    virtual_port_exists = False
    virtual_proto_exists = False

    for environment_variable in environment_variables:
      environment_variable_name, environment_variable_value = environment_variable.split('=')
      if environment_variable_name == VIRTUAL_HOST_ENV:
        virtual_host_exists = True
      elif environment_variable_name == VIRTUAL_PORT_ENV:
        virtual_port_exists = True
      elif environment_variable_name == VIRTUAL_PROTO_ENV:
        virtual_proto_exists = True

    if not virtual_host_exists:
      raise ScaffoldValidateException(f"VIRTUAL_HOST environment variable is missing from container: {container.name}")
    if not virtual_port_exists:
      raise ScaffoldValidateException(f"VIRTUAL_POST environment variable is missing from container: {container.name}")
    if not virtual_proto_exists:
      raise ScaffoldValidateException(f"VIRTUAL_PROTO environment variable is missing from container: {container.name}")

  
  def validate_proxy_container(self, service_proxy_container: Container):
    print(f"Validating proxy container: {service_proxy_container.name}")
    if not service_proxy_container.attrs:
      raise ScaffoldValidateException(f"Container attributes are missing for: {container.name}")

    if not self.service_config.detached:
      self.validate_fixtures_folder(service_proxy_container)

    self.proxy_environment_variables_exist(service_proxy_container)

  def validate_service_container(self):
    pass
  
  def validate(self) -> bool:
    print(f"Validating service: {self.service_name}")

    url = f"{self.service_config.scheme}://{self.hostname}"

    if self.service_config.hostname and self.workflow_name not in [WORKFLOW_TEST_TYPE]:
      self.validate_hostname(self.hostname, self.service_config.port)
    
    # Test workflow won't expose services that are detached and have a hostname to the host such as assets.
    # Need to test connection from inside the Docker network
    if self.service_config.hostname and self.workflow_name == WORKFLOW_TEST_TYPE and self.service_config.detached:
      self.validate_internal_hostname(url)

    self.validate_init_containers(self.service_docker_compose.init_container_name, self.service_docker_compose.configure_container_name)

    # Service init containers have a mounted dist folder unlike the core init container
    init_container = self.docker_client.containers.get(self.service_docker_compose.init_container_name)
    self.validate_fixtures_folder(init_container)

    if self.service_config.hostname:
      service_proxy_container = self.docker_client.containers.get(self.service_docker_compose.proxy_container_name)
      self.validate_proxy_container(service_proxy_container)

    if self.is_local():
      print(f"Validating local user defined service: {self.service_name}")
      # Validate docker-compose path exists
      docker_compose_path = f"{self.app_dir_path}/{DATA_DIR_NAME}/docker/{self.service_docker_compose.service_name}/{self.workflow_name}/docker-compose.yml"
      destination_path = Path(docker_compose_path)
      if not destination_path.is_file():
        raise ScaffoldValidateException(f"Docker compose path is not a file: {destination_path}")

      # Validate docker-compose.yml file has the service defined
      with open(destination_path) as f:
        if self.service_name not in f.read():
          raise ScaffoldValidateException(f"Local service is not defined in Docker Compose file: {destination_path}")

      service_container = self.docker_client.containers.get(self.service_docker_compose.container_name)
      if service_container.status == 'exited':
        return False

    if self.service_config.detached:
      service_container = self.docker_client.containers.get(self.service_docker_compose.container_name)
      self.validate_detached(service_container)

    print(f"Done validating service: {self.service_name}, success!")
    print()

    return True

