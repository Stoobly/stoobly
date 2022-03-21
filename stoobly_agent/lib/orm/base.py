from orator.orm import has_one

from . import ORM 

class Base(ORM.instance().base):

  @classmethod
  def where_for(cls, **kwargs):
    q = cls
    for key, val in kwargs.items():
      q = q.where(key, val)
    return q

  @classmethod
  def find_by(cls, **kwargs):
    return cls.where_for(**kwargs).first()
