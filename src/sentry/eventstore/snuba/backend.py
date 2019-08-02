from __future__ import absolute_import

from datetime import datetime
import six

from sentry.models import SnubaEvent
from sentry.utils import snuba
from sentry.eventstore.base import EventStorage


class SnubaEventStorage(EventStorage):
    """
    Eventstore backend backed by Snuba
    """

    def get_event_by_id(self, project_id, event_id, additional_columns=None):
        """
        Get an event given a project ID and event ID
        Returns None if an event cannot be found
        """
        cols = self.__get_columns(additional_columns)

        return SnubaEvent.get_event(project_id, event_id, snuba_cols=cols)

    def get_next_event_id(self, event, conditions=None, filter_keys=None):
        """
        Returns (project_id, event_id) of a next event given a current event
        and any filters/conditions. Returns None if no next event is found.
        """

        if not event:
            return None

        time_condition = [
            ['timestamp', '>=', event.timestamp],
            [['timestamp', '>', event.timestamp], ['event_id', '>', event.event_id]]
        ]

        conditions = conditions or []
        conditions.extend(time_condition)

        return self.__get_next_or_prev_event_id(
            start=event.datetime,
            end=datetime.utcnow(),
            conditions=conditions,
            filter_keys=filter_keys,
            orderby=['timestamp', 'event_id']
        )

    def get_prev_event_id(self, event, conditions=None, filter_keys=None):
        """
        Returns (project_id, event_id) of a previous event given a current event
        and any filters/conditions. Returns None if no previous event is found.
        """
        if not event:
            return None

        time_condition = [
            ['timestamp', '<=', event.timestamp],
            [['timestamp', '<', event.timestamp], ['event_id', '<', event.event_id]]
        ]
        conditions = conditions or []
        conditions.extend(time_condition)

        return self.__get_next_or_prev_event_id(
            end=event.datetime,
            start=datetime.utcfromtimestamp(0),
            conditions=conditions,
            filter_keys=filter_keys,
            orderby=['-timestamp', '-event_id']
        )

    def __get_columns(self, additional_columns):
        columns = EventStorage.minimal_columns

        if additional_columns:
            columns = set(columns + additional_columns)

        return [col.value for col in columns]

    def __get_next_or_prev_event_id(self, **kwargs):
        result = snuba.raw_query(
            selected_columns=['event_id', 'project_id'],
            limit=1,
            referrer='eventstore.get_next_or_prev_event_id',
            **kwargs
        )

        if 'error' in result or len(result['data']) == 0:
            return None

        row = result['data'][0]

        return (six.text_type(row['project_id']), six.text_type(row['event_id']))
