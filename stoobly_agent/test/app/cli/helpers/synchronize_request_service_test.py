import copy
import json
import pdb
import pytest

from stoobly_agent.app.cli.helpers.request_synchronize_handler import RequestSynchronizeHandler
from stoobly_agent.app.cli.helpers.synchronize_request_service import synchronize_component
from stoobly_agent.app.proxy.test.helpers.request_component_names_facade import RequestComponentNamesFacade
from stoobly_agent.app.settings.constants import request_component
from stoobly_agent.test.mock_data.endpoint_show_response import endpoint_show_response

class TestSynchronizeRequestService():
  @pytest.fixture(scope='class')
  def request_synchronize_handler(self):
    return RequestSynchronizeHandler(request_component.RESPONSE_PARAM, {})

  class TestWhenAdding():

    @pytest.fixture(scope='function')
    def response_param_names_facade(self):
      response_param_names = copy.deepcopy(endpoint_show_response['response_param_names'])
      aliases = copy.deepcopy(endpoint_show_response['aliases'])

      facade = RequestComponentNamesFacade(response_param_names).with_aliases(aliases)
      return facade

    def test_array_of_object_one_property(self, response_param_names_facade: RequestComponentNamesFacade, request_synchronize_handler: RequestSynchronizeHandler):
      self.__decorate_with_values(response_param_names_facade, '[*].id', [934])

      response = [{}]
      synchronize_component(response, response_param_names_facade, request_synchronize_handler)

      assert self.__equals(response, [{'id': 934}]), print(response)

    def test_array_of_object_two_property(self, response_param_names_facade: RequestComponentNamesFacade, request_synchronize_handler: RequestSynchronizeHandler):
      self.__decorate_with_values(response_param_names_facade, '[*].id', [934])
      self.__decorate_with_values(response_param_names_facade, '[*].category', [1])

      response = [{}]
      synchronize_component(response, response_param_names_facade, request_synchronize_handler)

      assert self.__equals(response, [{'category': 1, 'id': 934}]), print(response)

    def test_array_of_objects_one_property(self, response_param_names_facade: RequestComponentNamesFacade, request_synchronize_handler: RequestSynchronizeHandler):
      self.__decorate_with_values(response_param_names_facade, '[*].id', [934])

      response = [{}, {}]
      synchronize_component(response, response_param_names_facade, request_synchronize_handler)

      assert self.__equals(response, [{'id': 934}, {'id': 934}]), print(response)

    def __decorate_with_values(self, facade: RequestComponentNamesFacade, query: str, value):
      facade.query_index[query]['values'] = value

    def __equals(self, a, b):
      return json.dumps(a) == json.dumps(b)

  class TestWhenRemoving():
    @pytest.fixture(scope='function')
    def response_param_names_facade(self):
      response_param_names = copy.deepcopy(endpoint_show_response['response_param_names'])
      aliases = copy.deepcopy(endpoint_show_response['aliases'])

      facade = RequestComponentNamesFacade(response_param_names).with_aliases(aliases)
      return facade

    def test_array_of_object_one_property(self, response_param_names_facade: RequestComponentNamesFacade, request_synchronize_handler: RequestSynchronizeHandler):
      response = [{'remove': 1}]
      synchronize_component(response, response_param_names_facade, request_synchronize_handler)

      assert self.__equals(response, [{}]), print(response) 

    def test_object_two_properties(self, response_param_names_facade: RequestComponentNamesFacade, request_synchronize_handler: RequestSynchronizeHandler):
      response = [{'id': 1, 'remove': 1, 'remove2': 1}]
      synchronize_component(response, response_param_names_facade, request_synchronize_handler)

      assert self.__equals(response, [{'id': 1}]), print(response) 

    def __equals(self, a, b):
      return json.dumps(a) == json.dumps(b)