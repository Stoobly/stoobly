from base64 import b64encode
import pdb
from re import I

from httptools import HttpRequestParser, parse_url
from typing import List
from urllib.parse import parse_qs

from stoobly_agent.app.models.adapters.types.request_show_params import RequestShowParams
from stoobly_agent.lib.api.interfaces import QueryParam, RequestShowResponse, ResponseShowResponse

from ..request import Request as ORMRequest
from ..response import Response
from ..utils.request_parse_handler import Request as RequestDict, RequestParseHandler
from .orm_to_stoobly_response_transformer import ORMToStooblyResponseTransformer

FILTER_LIST = [
  'headers_hash',
  'body_text_hash',
  'query_params_hash',
  'body_params_hash',
  'control',
  'raw',
] 

class ORMToStooblyRequestTransformer():
  __options: RequestShowParams
  __request: ORMRequest = None

  # TODO: filter by options
  def __init__(self, request: ORMRequest, options: RequestShowParams):
    self.__options = options
    self.__request = request

  def transform(self) -> RequestShowResponse:
    stoobly_request: RequestShowResponse = self.__request.to_dict()

    self.__decorate_with_request(stoobly_request, self.__request)
    self.__decorate_with_response(stoobly_request, self.__request.response)
    self.__decorate_with_components(stoobly_request, self.__request)
    self.__decorate_with_scenario(stoobly_request, self.__request)
    
    return self.__filter_properties(stoobly_request)

  def __filter_properties(self, stoobly_request: RequestShowResponse):
    allowed_keys = list(RequestShowResponse.__annotations__.keys()) + [
      'committed_at', 'body_params_hash', 'body_text_hash', 'key', 'query', 'query_params_hash'
    ]

    filter_keys = lambda request: dict((key, value) for key, value in request.items() if key in allowed_keys)
    return filter_keys(stoobly_request)

  def __decorate_with_scenario(self, stoobly_request: RequestShowResponse, request: ORMRequest):
    if not request.scenario_id:
      return

    scenario = request.scenario
    stoobly_request['scenario'] = scenario.name

  def __decorate_with_components(self, stoobly_request: RequestShowResponse, request: ORMRequest):
    components = []
    if len(request.query_params_hash) != 0:
      components.append('query_params')

    if len(request.body_params_hash) != 0:
      components.append('body_params')

    if len(request.body_text_hash) != 0:
      components.append('body')

    stoobly_request['components'] = components

  def __decorate_with_request(self, stoobly_request: RequestShowResponse, request: ORMRequest):
    request_dict = self.__parse_raw_request(request.raw)

    stoobly_request['method'] = request_dict['method'].decode()
    stoobly_request['url'] = request_dict['url'].decode()

    if 'headers' in self.__options:
      stoobly_request['headers'] = self.__transform_headers(request_dict['headers'])

    if 'body' in self.__options:
      stoobly_request['body'] = b64encode(request_dict['body'])

    parsed_url = parse_url(request_dict['url'])

    if parsed_url.query:
      stoobly_request['query'] = parsed_url.query.decode()
      if 'query_params' in self.__options:
        stoobly_request['query_params'] = self.__transform_query_params(parsed_url.query)

  def __transform_headers(self, headers: dict):
    headers_list = []
    for key, val in headers.items():
      headers_list.append({
        'name': key,
        'value': val,
      })
    return headers_list

  def __transform_query_params(self, query_params):
    query_params_list: List[QueryParam] = []

    for key, val in parse_qs(query_params).items():
      query_params_list.append({
        'name': key,
        'value': val,
      })
    return query_params_list

  def __parse_raw_request(self, raw_request: bytes):
    request_dict = {}
    handler = RequestParseHandler(request_dict)
    parser = HttpRequestParser(handler)
    parser.feed_data(memoryview(raw_request))
    request_dict['method'] = parser.get_method()
    return request_dict
  
  def __decorate_with_response(self, stoobly_request: RequestShowResponse, orm_response: Response):
    if not orm_response:
      return

    transformer = ORMToStooblyResponseTransformer(orm_response)
    stoobly_request['status'] = int(transformer.python_response.status_code)

    if 'response' in self.__options:
      stoobly_response = transformer.transform()
      stoobly_request['response'] = stoobly_response
