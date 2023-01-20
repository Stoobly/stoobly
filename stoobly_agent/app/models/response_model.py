import pdb
import requests

from stoobly_agent.app.models.adapters.response_adapter_factory import ResponseAdapterFactory
from stoobly_agent.app.settings import Settings
from stoobly_agent.lib.logger import Logger

from .model import Model

class ResponseModel(Model):

  def __init__(self, settings: Settings):
    super().__init__(settings)

  def as_local(self):
    self.adapter =  ResponseAdapterFactory(self.settings.remote).local_db()

  def as_remote(self):
    # raise('Not yet supported.')
    pass

  def mock(self, request_id: str) -> requests.Response:
    try:
      return self.adapter.mock(request_id)
    except requests.exceptions.RequestException as e:
      self.__handle_request_error(e)
      return None

  def __handle_request_error(self, e: requests.exceptions.RequestException):
      response: requests.Response = e.response
      if response:
        Logger.instance().error(f"{response.status_code} {response.content}")