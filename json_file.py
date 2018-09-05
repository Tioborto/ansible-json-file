# (c) 2018, Alexandre Bortoluzzi
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
    callback: json_file
    short_description: Ansible screen output to json file
    version_added: "2.6"
    description:
        - This callback converts all events into JSON output to file
    type: stdout
    requirements:
      - Set as stdout in config
      - Set ANSIBLE_LOG_FILE_NAME variable
    options:
      log_file_name:
        version_added: "2.6"
        name: Show custom stats
        description: 'This is the file to write JSON output'
        default: False
        env:
          - name: ANSIBLE_LOG_FILE_NAME
        type: bool
'''

import datetime
import json
import os
from functools import partial
from ansible.inventory.host import Host
from ansible.plugins.callback import CallbackBase
from ansible.module_utils._text import to_native

def current_time():
    return '%sZ' % datetime.datetime.utcnow().isoformat()

class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'json_file'

    def __init__(self, display=None):
        super(CallbackModule, self).__init__(display)
        self.log_file_name = os.getenv('ANSIBLE_LOG_FILE_NAME', '')
        self.results = []

    def _new_play(self, play):
        return {
            'play': {
                'name': play.get_name(),
                'id': str(play._uuid),
                'duration': {
                    'start': current_time()
                }
            },
            'tasks': []
        }

    def _new_task(self, task):
        return {
            'task': {
                'name': task.get_name(),
                'id': str(task._uuid),
                'duration': {
                    'start': current_time()
                }
            },
            'hosts': {}
        }

    def v2_playbook_on_play_start(self, play):
        self.results.append(self._new_play(play))

    def v2_playbook_on_task_start(self, task, is_conditional):
        self.results[-1]['tasks'].append(self._new_task(task))

    def v2_playbook_on_handler_task_start(self, task):
        self.results[-1]['tasks'].append(self._new_task(task))

    def _convert_host_to_name(self, key):
        if isinstance(key, (Host,)):
            return key.get_name()
        return key

    def v2_playbook_on_stats(self, stats):
        """Display info about playbook statistics"""

        hosts = sorted(stats.processed.keys())

        summary = {}
        for h in hosts:
            s = stats.summarize(h)
            summary[h] = s

        output = {
            'plays': self.results,
            'stats': summary,
        }

        try:
            output_file = open("{0}".format(self.log_file_name),"w+")
            output_file.write(json.dumps(output, indent=4, sort_keys=True))
            output_file.close()
        except Exception as e:
            AnsibleError('Something happened, this was original exception: %s' % to_native(e))

    def _record_task_result(self, on_info, result, **kwargs):
        """This function is used as a partial to add failed/skipped info in a single method"""
        host = result._host
        task = result._task
        task_result = result._result.copy()
        task_result.update(on_info)
        task_result['action'] = task.action
        self.results[-1]['tasks'][-1]['hosts'][host.name] = task_result
        end_time = current_time()
        self.results[-1]['tasks'][-1]['task']['duration']['end'] = end_time
        self.results[-1]['play']['duration']['end'] = end_time

    def __getattribute__(self, name):
        """Return ``_record_task_result`` partial with a dict containing skipped/failed if necessary"""
        if name not in ('v2_runner_on_ok', 'v2_runner_on_failed', 'v2_runner_on_unreachable', 'v2_runner_on_skipped'):
            return object.__getattribute__(self, name)

        on = name.rsplit('_', 1)[1]

        on_info = {}
        if on in ('failed', 'skipped'):
            on_info[on] = True

        return partial(self._record_task_result, on_info)
