import pdb
import requests

from typing import Union

from stoobly_agent.lib.logger import Logger
from stoobly_agent.app.settings import Settings

from .adapters.response_header_adapter_factory import ResponseHeaderAdapterFactory
from .types.requests_model_index import RequestsModelIndex

class ResponseHeaderModel():

  def __init__(self, settings: Settings):
    if not settings.cli.features.remote:
      self.adapter =  ResponseHeaderAdapterFactory(settings.remote).local_db()
    else:
      raise('Not yet supported.')

    self.settings = settings

  def index(self, request_id: str, **query_params) -> Union[RequestsModelIndex, None]:
    try:
      return self.adapter.index(request_id, **query_params)
    except requests.exceptions.RequestException as e:
      self.__handle_request_error(e)
      return None

  def __handle_request_error(self, e: requests.exceptions.RequestException):
      response: requests.Response = e.response
      if response:
        Logger.instance().error(f"{response.status_code} {response.content}")