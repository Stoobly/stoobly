import pdb
from stoobly_agent.lib.api.schemas.request import Request

from stoobly_agent.lib.settings import Settings
from stoobly_agent.lib.api.requests_resource import RequestsResource
from stoobly_agent.lib.api.scenarios_resource import ScenariosResource
from stoobly_agent.lib.intercept_handler.constants import modes, test_strategies
from stoobly_agent.lib.intercept_handler.replay.replay_scenario_service import replay

class Scenario():

  def __init__(self, settings: Settings):
    self.settings = settings

  def index(self, project_key, **kwargs):
    api = ScenariosResource(self.settings.api_url, self.settings.api_key)
    res = api.from_project_key(
      project_key, lambda project_id: api.index(project_id, kwargs)
    ) 
    return res.json()

  def replay(self, scenario_key: str, **kwargs):
    kwargs['mode'] = modes.NONE
    self.__replay(scenario_key, **kwargs)

  def test(self, scenario_key: str, **kwargs):
    kwargs['mode'] = modes.TEST
    kwargs['report_key'] = kwargs.get('save_to_report')
    kwargs['strategy'] = kwargs.get('strategy') or test_strategies.DIFF

    self.__replay(scenario_key, **kwargs)

  def __replay(self, scenario_key: str, **kwargs):
    kwargs['scenario_key'] = scenario_key

    replay(
      RequestsResource(self.settings.api_url, self.settings.api_key), **kwargs
    )

