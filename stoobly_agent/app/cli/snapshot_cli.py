import click
import datetime
import pdb
import os
import re
import requests

from urllib.parse import urlparse

from stoobly_agent.app.models.adapters.raw_joined import RawJoinedRequestAdapterFactory
from stoobly_agent.app.models.factories.resource.local_db.helpers.log import Log
from stoobly_agent.app.models.factories.resource.local_db.helpers.log_event import LogEvent, REQUEST_RESOURCE, SCENARIO_RESOURCE
from stoobly_agent.app.models.factories.resource.local_db.helpers.request_snapshot import RequestSnapshot
from stoobly_agent.app.models.factories.resource.local_db.helpers.scenario_snapshot import ScenarioSnapshot
from stoobly_agent.app.models.helpers.apply import Apply

from .helpers.print_service import print_snapshots
from .helpers.verify_raw_request_service import verify_raw_request

@click.group(
    epilog="Run 'stoobly-agent project COMMAND --help' for more information on a command.",
    help="Manage snapshots"
)
@click.pass_context
def snapshot(ctx):
    pass

@snapshot.command(
  help="Apply snapshots",
)
@click.option('--force', default=False, help="Toggles whether resources are hard deleted.")
@click.argument('uuid', required=False)
def apply(**kwargs):
  apply = Apply(force=kwargs['force']).with_logger(print)

  if kwargs.get('uuid'):
    apply.single(kwargs['uuid'])
  else:
    apply.all()

@snapshot.command(
  help="List snapshots",
  name="list"
)
@click.option('--pending', default=False, is_flag=True, help='Lists not yet processed snapshots.')
@click.option(
  '--resource',
  default=REQUEST_RESOURCE,
  type=click.Choice([REQUEST_RESOURCE, SCENARIO_RESOURCE]),
  help=f"Defaults to {REQUEST_RESOURCE}."
)
@click.option('--search', help='Regex pattern to filter snapshots by.')
@click.option('--select', multiple=True, help='Select column(s) to display.')
@click.option('--without-headers', is_flag=True, default=False, help='Disable printing column headers.')
def _list(**kwargs):
  log = Log()

  events = None
  if kwargs.get('pending'):
    events = log.unprocessed_events
  else:
    events = log.target_events

  __print_events(events, **kwargs)

@snapshot.command(
  help="Update snapshot",
)
@click.option('--verify', is_flag=True, default=False)
@click.argument('uuid')
def update(**kwargs):
  log = Log()

  events = []
  for event in log.target_events:
    if event.uuid != kwargs['uuid']:
      continue

    if kwargs['verify']:
      if event.is_request(): 
        snapshot: RequestSnapshot = event.snapshot()
        __verify_request(snapshot)
      elif event.is_scenario():
        snapshot: ScenarioSnapshot = event.snapshot()
        snapshot.iter_request_snapshots(__verify_request)

    new_event = event.duplicate()
    log.append(str(new_event))
    events.append(new_event)

  if events:
    __print_events(events)

def __print_events(events, **kwargs):
  formatted_events = []
  if kwargs.get('resource') == SCENARIO_RESOURCE:
    for event in events:
      if event.resource != SCENARIO_RESOURCE:
        continue

      snapshot = event.snapshot()
      if not __scenario_matches(snapshot, kwargs.get('search')):
        continue

      path = os.path.relpath(snapshot.metadata_path)

      formatted_events.append({
        **__transform_scenario(snapshot),
        'snapshot': path,
        **__transform_event(event),
      })
  else:
    for event in events:
      if event.resource != REQUEST_RESOURCE:
        continue
      
      snapshot = event.snapshot()
      request = __to_request(snapshot)

      if not __request_matches(request, kwargs.get('search')):
        continue

      path = os.path.relpath(snapshot.path)

      formatted_events.append({
        **__transform_request(request),
        'snapshot': path,
        **__transform_event(event),
      })

  if len(formatted_events):
    print_snapshots(formatted_events, **kwargs)

def __verify_request(snapshot: RequestSnapshot):
  raw_request = snapshot.request
  if not raw_request:
    return

  verified_raw_request = verify_raw_request(raw_request)

  if raw_request != verified_raw_request:
    snapshot.write_raw(verified_raw_request)

def __transform_event(event: LogEvent):
  event_dict = {}

  event_dict['uuid'] = event.uuid
  event_dict['action'] = event.action

  if event.created_at:
    event_dict['created_at'] = datetime.datetime.fromtimestamp(event.created_at / 1000)

  return event_dict

def __to_request(snapshot: RequestSnapshot):
  raw_request = snapshot.request
  if not raw_request:
    return None

  return RawJoinedRequestAdapterFactory(raw_request).python_request()

def __request_matches(request: requests.Request, search: str):
  if not search:
    return True
  
  if not request:
    return False

  uri = urlparse(request.url)
  return re.match(search, request.url) or re.match(search, uri.path)

def __transform_request(request: requests.Request):
  event_dict = { 'method': '', 'host': '', 'port': '', 'path': '', 'query': ''}

  if request:
    uri = urlparse(request.url)
    event_dict['method'] = request.method
    event_dict['host'] = uri.hostname
    event_dict['port'] = uri.port
    event_dict['path'] = uri.path
    event_dict['query'] = uri.query

  return event_dict

def __scenario_matches(snapshot: ScenarioSnapshot, search: str):
  if not search:
    return True

  metadata = snapshot.metadata
  return re.match(search, metadata.get('name') or '')

def __transform_scenario(snapshot: ScenarioSnapshot):
  event_dict = {}

  metadata = snapshot.metadata
  event_dict['name'] = metadata.get('name')
  event_dict['description'] = metadata.get('description')

  return event_dict