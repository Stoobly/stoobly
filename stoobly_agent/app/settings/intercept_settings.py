import os

from stoobly_agent.config.constants import env_vars
from stoobly_agent.config.constants import mode

from .types.proxy_settings import InterceptSettings as IInterceptSettings

class InterceptSettings:
  __intercept_settings = None

  def __init__(self, intercept_settings: IInterceptSettings):
    self.__intercept_settings = intercept_settings or {}

    self.__active = self.__intercept_settings.get('active')
    self.__mode = self.mode_before_change
    self.__project_key = self.__intercept_settings.get('project_key')
    self.__upstream_url = self.__intercept_settings.get('upstream_url')

  @property
  def active(self):
    return self.__active

  @property
  def mode_before_change(self):
    return self.__intercept_settings.get('mode') or mode.NONE

  @property
  def mode(self):
    if self.__mode != self.mode_before_change:
      return self.__mode

    if os.environ.get(env_vars.AGENT_ACTIVE_MODE):
        return os.environ[env_vars.AGENT_ACTIVE_MODE]
        
    return self.__mode

  @mode.setter
  def mode(self, v):
    if v in [mode.MOCK, mode.NONE, mode.RECORD, mode.TEST]:
      self.__mode = v

  @property
  def project_key(self):
    return self.__project_key

  @property
  def upstream_url(self):
    return self.__upstream_url

  def to_dict(self) -> IInterceptSettings:
    return {
      'active': self.__active,
      'mode': self.__mode,
      'project_key': self.__project_key,
      'upstream_url': self.__upstream_url,
    }