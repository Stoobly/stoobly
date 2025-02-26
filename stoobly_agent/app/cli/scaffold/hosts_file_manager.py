import os
import tempfile
import pdb
import platform
from dataclasses import dataclass
from typing import Union


class HostsFileManager():

  @dataclass
  class IpAddressToHostnames:
    ip_address: str
    hostnames: list[str]

  SCAFFOLD_HOSTS_DELIMITTER_BEGIN = "##### STOOBLY SCAFFOLD HOSTS BEGIN #####\n"
  SCAFFOLD_HOSTS_DELIMITTER_END = "##### STOOBLY SCAFFOLD HOSTS END #####\n"

  def __get_hosts_file_path(self) -> str:
    system = platform.system()
    if system == 'Linux' or system == 'Darwin':
      return '/etc/hosts'
    else:
      print(f"Unsupported system: {system}, for hosts file validation, skipping")

    return ''

  # Split IP address and hostnames. Don't include inline comments
  def __split_hosts_line(self, line: str) -> list[str]:
    ip_addr_hosts_split = line.split('#')[0].split()
    return ip_addr_hosts_split


  # Parses hosts file and returns a mapping of IP address to hostnames in a list.
  def get_hosts(self) -> list[IpAddressToHostnames]:
    hosts_file_path = self.__get_hosts_file_path()

    if not hosts_file_path:
      return []

    with open(hosts_file_path, 'r') as f:
      hostlines = f.readlines()

    # Skip comments and empty lines
    hostlines = [line.strip() for line in hostlines
                 if not line.startswith('#') and line.strip() != '']

    hosts = []
    for line in hostlines:
      ip_addr_hosts_split = self.__split_hosts_line(line)
      ip_address = ip_addr_hosts_split[0]
      hostnames = ip_addr_hosts_split[1:]
      ipAddressToHostnames = self.IpAddressToHostnames(ip_address, hostnames)

      hosts.append(ipAddressToHostnames)

    return hosts

  def find_host(self, hostname) -> Union[IpAddressToHostnames, None]:
    hosts = self.get_hosts()

    for mapping in hosts:
      if ((mapping.ip_address == '0.0.0.0' or mapping.ip_address == '127.0.0.1') and
        hostname in mapping.hostnames):

        return mapping

    return None

  def install_hostnames(self, hostnames: list[str]) -> None:
    # Remove the scaffold service hostnames to prevent duplicates
    self.uninstall_hostnames(hostnames)

    hosts_file_path = self.__get_hosts_file_path()

    with open(hosts_file_path, 'a+') as f:
      if self.SCAFFOLD_HOSTS_DELIMITTER_BEGIN not in f.read():
        f.write(self.SCAFFOLD_HOSTS_DELIMITTER_BEGIN)

      for hostname in hostnames:
        print(f"Writing hostname {hostname} to {hosts_file_path}")
        f.write(f"0.0.0.0 {hostname}\n")

      if self.SCAFFOLD_HOSTS_DELIMITTER_END not in f.read():
        f.write(self.SCAFFOLD_HOSTS_DELIMITTER_END)

    print(f"Successfully installed hostnames to {hosts_file_path}")

  def uninstall_hostnames(self, hostnames: list[str]) -> None:
    hosts_file_path = self.__get_hosts_file_path()

    print(f"Deleting hostnames from {hosts_file_path}")

    temp_file_path = ""
    try:
      # Create a temporary file in the system's temp directory
      with tempfile.NamedTemporaryFile('w', delete=False) as temp:
        temp_file_path = temp.name

        # Read the original hosts file and write filtered lines to the temp file
        with open(hosts_file_path, 'r') as original:
          for line in original:
            for hostname in hostnames:
              if (not line.startswith(f"0.0.0.0 {hostname}") and
                not line.startswith(self.SCAFFOLD_HOSTS_DELIMITTER_BEGIN) and
                not line.startswith(self.SCAFFOLD_HOSTS_DELIMITTER_END)):

                temp.write(line)

      # Atomically replace the original hosts file with the temp file
      if temp_file_path:
        os.replace(temp_file_path, hosts_file_path)
        print(f"Successfully uninstalled hostnames from {hosts_file_path}")

    finally:
      # Clean up the temp file if it wasn't moved
      if os.path.exists(temp_file_path):
        os.remove(temp_file_path)

    return None

