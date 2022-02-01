import time

from mitmproxy.http import HTTPFlow as MitmproxyHTTPFlow
from requests import Response
from typing import Union

from ..settings import IProjectMockSettings, IProjectTestSettings 
from ..stoobly_api import StooblyApi

class MockContext():
  def __init__(self, flow: MitmproxyHTTPFlow, active_mode_settings: Union[IProjectMockSettings , IProjectTestSettings]):
    self.active_mode_settings = active_mode_settings
    self.flow = flow
    self.start_time = time.time()

    self.api = None
    self.response = None

  def with_response(self, response: Response):
    self.response = response
    return self

  def with_api(self, api: StooblyApi):
    self.api = api
    return self