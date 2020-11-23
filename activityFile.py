import mapadroid.utils.pluginBase
from flask import render_template, Blueprint
from mapadroid.madmin.functions import auth_required
import os
import time
from datetime import datetime

import logging
import socket
import select
import json
import sys
import ast
from threading import Thread
from pathlib import Path

from mapadroid.utils.madGlobals import WebsocketWorkerRemovedException, \
        WebsocketWorkerTimeoutException, WebsocketWorkerConnectionClosedException, \
        InternalStopWorkerException


class activityFile(mapadroid.utils.pluginBase.Plugin):
    """activityFile plugin
    """
    def __init__(self, mad):
        super().__init__(mad)

        self._rootdir = os.path.dirname(os.path.abspath(__file__))

        self._mad = mad
        self.logger = self._mad['logger']
        self.db = self._mad["db_wrapper"]
        
        self.statusname = self._mad["args"].status_name
        self._pluginconfig.read(self._rootdir + "/plugin.ini")
        self._versionconfig.read(self._rootdir + "/version.mpl")
        self.author = self._versionconfig.get("plugin", "author", fallback="unknown")
        self.url = self._versionconfig.get("plugin", "url", fallback="https://www.maddev.eu")
        self.description = self._versionconfig.get("plugin", "description", fallback="unknown")
        self.version = self._versionconfig.get("plugin", "version", fallback="unknown")
        self.pluginname = self._versionconfig.get("plugin", "pluginname", fallback="https://www.maddev.eu")
        self.staticpath = self._rootdir + "/static/"
        self.templatepath = self._rootdir + "/template/"

        # plugin specific
        if self.statusname in self._pluginconfig:
            self.logger.success("Applying specific config for status-name {}!", self.statusname)
            settings = self.statusname
        else:
            self.logger.info("Using generic settings on instance with status-name {}", self.statusname)
            settings = "settings"

        self.interval = self._pluginconfig.getint(settings, "interval", fallback=60)
        self.successlog = self._pluginconfig.getboolean(settings, "successlog", fallback=True)
        self.ws_server = self._mad['ws_server']
        self.args = self._mad['args']


        self._routes = [
            ("/activityFile_manual", self.manual),
        ]

        self._hotlink = [
            ("activityFile Manual", "activityFile_manual", "activityFile Manual"),
        ]

        if self._pluginconfig.getboolean("plugin", "active", fallback=False):
            self._plugin = Blueprint(str(self.pluginname), __name__, static_folder=self.staticpath,
                                     template_folder=self.templatepath)

            for route, view_func in self._routes:
                self._plugin.add_url_rule(route, route.replace("/", ""), view_func=view_func)

            for name, link, description in self._hotlink:
                self._mad['madmin'].add_plugin_hotlink(name, self._plugin.name+"."+link.replace("/", ""),
                                                       self.pluginname, self.description, self.author, self.url,
                                                       description, self.version)

    def perform_operation(self):
        # do not change this part ▽▽▽▽▽▽▽▽▽▽▽▽▽▽▽
        if not self._pluginconfig.getboolean("plugin", "active", fallback=False):
            return False
        self._mad['madmin'].register_plugin(self._plugin)
        # do not change this part △△△△△△△△△△△△△△△

        # load your stuff now
        self.logger.success("activityFile Plugin starting operations ...")
        activityFile = Thread(name="activityFile", target=self.activityFile,)
        activityFile.daemon = True
        activityFile.start()

        return True


    def activityFile(self):
        while True:
            devices = self.ws_server.get_reg_origins()
            loglist = []
            for device in devices:
                # touch file
                Path(os.path.join(self.args.file_path, str(device) + '.active')).touch()
                # details for logging
                communicator = self.ws_server.get_origin_communicator(device)
                entry = communicator.websocket_client_entry
                timestamp = entry.last_message_received_at
                loglist.append((device, datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')))
            if self.successlog:
                loglist = sorted(loglist, key=lambda x: x[1], reverse=True)
                self.logger.success("touched {} devices: {}", len(loglist), loglist)
            time.sleep(self.interval)


    @auth_required
    def manual(self):
        return render_template("activityFile_manual.html",
                               header="activityFile manual", title="activityFile manual"
                               )

