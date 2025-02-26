import pdb
import pytest

from stoobly_agent.app.cli.scaffold.hosts_file_manager import HostsFileManager


class TestHostsFileManager():

  @pytest.fixture
  def hosts_file_manager(self):
    yield HostsFileManager()

  def test_get_hosts_file_path(self, hosts_file_manager):
    hosts_file_path = hosts_file_manager._HostsFileManager__get_hosts_file_path()

    # Test runners are all Linux distros for now
    assert hosts_file_path == '/etc/hosts'

  def test_get_hosts(self, hosts_file_manager):
    hosts = hosts_file_manager.get_hosts()

    assert hosts
    assert len(hosts) > 1

    localhost_found = False
    for host in hosts:
      if host.ip_address == '127.0.0.1' and 'localhost' in host.hostnames:
        localhost_found = True
        break
    assert localhost_found

  def test_find_host(self, hosts_file_manager):
    url = 'localhost'

    host = hosts_file_manager.find_host(url)

    assert host
    assert host.ip_address == '127.0.0.1'
    assert 'localhost' in host.hostnames


  class TestsSplitHostsLine():
    def test_basic(self, hosts_file_manager):
      line = '0.0.0.0 example.com'
      split = hosts_file_manager._HostsFileManager__split_hosts_line(line)

      assert split[0] == '0.0.0.0'
      assert split[1] == 'example.com'

    def test_tabs(self, hosts_file_manager):
      line = '0.0.0.0\texample.com'
      split = hosts_file_manager._HostsFileManager__split_hosts_line(line)

      assert split[0] == '0.0.0.0'
      assert split[1] == 'example.com'

    def test_comment(self, hosts_file_manager):
      line = '# 0.0.0.0 example.com'
      split = hosts_file_manager._HostsFileManager__split_hosts_line(line)

      assert len(split) == 0

    def test_inline_comment(self, hosts_file_manager):
      line = '0.0.0.0\texample.com # Comment'
      split = hosts_file_manager._HostsFileManager__split_hosts_line(line)

      assert split[0] == '0.0.0.0'
      assert split[1] == 'example.com'

    def test_multiple_hostnames(self, hosts_file_manager):
      line = '0.0.0.0\texample.com example2.com example3.com # Comment'
      split = hosts_file_manager._HostsFileManager__split_hosts_line(line)

      assert split[0] == '0.0.0.0'
      assert split[1] == 'example.com'
      assert split[2] == 'example2.com'
      assert split[3] == 'example3.com'


