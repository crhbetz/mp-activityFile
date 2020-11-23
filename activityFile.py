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
import requests
import configparser

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
        self.logger.success("{} Plugin starting operations ...", self.pluginname)
        activityFile = Thread(name=self.pluginname, target=self.activityFile,)
        activityFile.daemon = True
        activityFile.start()

        updateChecker = Thread(name="{}Updates".format(self.pluginname), target=self.update_checker,)
        updateChecker.daemon = True
        updateChecker.start()

        return True

    def _is_update_available(self):
        update_available = None
        try:
            raw_url = self.url.replace("github.com", "raw.githubusercontent.com")
            r = requests.get("{}/main/version.mpl".format(raw_url))
            self.github_mpl = configparser.ConfigParser()
            self.github_mpl.read_string(r.text)
            self.available_version = self.github_mpl.get("plugin", "version", fallback=self.version)
        except Exception as e:
            return None

        try:
            from pkg_resources import parse_version
            update_available = parse_version(self.version) < parse_version(self.available_version)
        except Exception:
            pass

        if update_available is None:
            try:
                from distutils.version import LooseVersion
                update_available = LooseVersion(self.version) < LooseVersion(self.available_version)
            except Exception:
                pass

        if update_available is None:
            try:
                from packaging import version
                update_available = version.parse(self.version) < version.parse(self.available_version)
            except Exception:
                pass

        return update_available


    def update_checker(self):
        while True:
            self.logger.debug("{} checking for updates ...", self.pluginname)
            result = self._is_update_available()
            if result:
                self.logger.warning("An update of {} from version {} to version {} is available!",
                                    self.pluginname, self.version, self.available_version)
            elif result is False:
                self.logger.success("{} is up-to-date! ({} = {})", self.pluginname, self.version,
                                    self.available_version)
            else:
                self.logger.warning("Failed checking for updates!")
            time.sleep(3600)


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

