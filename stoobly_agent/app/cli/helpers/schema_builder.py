import pdb

from typing import Union

from stoobly_agent.lib.api.interfaces.endpoints import RequestComponentName
from stoobly_agent.lib.utils.python_to_ruby_type import convert

class SchemaBuilder:
  ###
  #
  # @param endpoint_id [Integer]
  # @param param_name_class [QueryParamName, BodyParamName, ResponseParamName]
  # @param param_column_name [String] e.g. query_param_name, body_param_name, response_param_name
  #
  def __init__(self, endpoint_id, param_column_name: str):
    self.endpoint_id = endpoint_id
    self.param_column_name: str = param_column_name

  def build(self, params):
    self.param_names_created = {}
    self.__traverse('', params, None)
    return self.param_names_created.values()

  ###
  #
  # @param name [String] name of current param
  # @param value [Object] value of current param
  # @param param [QueryParamName, BodyParamName, ResponseParamName] parent param record
  #
  def __traverse(self, name: str, value, param: RequestComponentName):

    if type(value) is list:
      self.__traverse_array(name, value, param)
    elif type(value) is dict:
      self.__traverse_hash(name, value, param)

    # if value['inferred_type'] == 'Array':
    #   return self.__traverse_array(name, value, param)
    # if value['inferred_type'] == 'Hash':
    #   return self.__traverse_hash(name, value, param)

  def __traverse_array(self, name: str, value, parent_param: RequestComponentName):
    columns = {
      'endpoint_id': self.endpoint_id,
      'name':  f"{name.capitalize()}Element",
      'query': f"{parent_param.get('query')}[*]" if parent_param else '[*]'
    }
    columns[self.param_column_name + '_id'] = parent_param['id'] if parent_param else None

    # Iterate
    types = {}
    for e in value:
      _type = self.__infer_type(e)

      if types.get(_type) is None:
        columns['inferred_type'] = convert(_type)
        types[_type] = self.__find_or_create_by(columns)
    
      self.__traverse('', e, types[_type])

  def __traverse_hash(self, name, value, parent_param: RequestComponentName):
    # Iterate
    for k, v in value.items():
      columns = {
        'endpoint_id': self.endpoint_id,
        'inferred_type': convert(self.__infer_type(v)),
        'is_required': v is not None,
        'name': k,
        'query': f"{parent_param.get('query')}.{k}" if parent_param else k, 
      }
      columns[self.param_column_name + '_id'] = parent_param['id'] if parent_param else None
      param = self.__find_or_create_by(columns)

      self.__traverse(k, v, param)

  def __find_or_create_by(self, columns):
    param = self.__find_by(columns) 

    if param is None:
      param = self.__create(columns)

    return param

  def __find_by(self, columns) -> Union[RequestComponentName, None]:
    for id, param_name in self.param_names_created.items():
      matches = True

      for key in columns:
        if key not in param_name:
          matches = False
          break

        if param_name[key] != columns[key]:
          matches = False
          break
      
      if matches:
        return param_name

  def __create(self, columns):
    param: RequestComponentName = columns.copy()
    param['id'] = len(self.param_names_created.keys()) + 1

    self.param_names_created[param['id']] = param

    return param

  def __infer_type(self, val) -> str:
    return str(val.__class__)