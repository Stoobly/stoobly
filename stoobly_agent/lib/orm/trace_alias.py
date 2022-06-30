from orator.orm import belongs_to

from . import ORM

class TraceAlias(ORM.instance().base):
  __fillable__ = ['assigned_to', 'name', 'trace_id', 'value']

  @belongs_to
  def trace(self):
    from .trace import Trace # Get around circular import
    return Trace

  @belongs_to
  def trace_request(self):
    from .trace_request import TraceRequest
    return TraceRequest