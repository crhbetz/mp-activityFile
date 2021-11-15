import mapadroid.plugins.pluginBase
import os
import time
from datetime import datetime

import logging
import socket
import select
import json
import sys
import ast
from pathlib import Path
import requests
import configparser
import asyncio
from aiohttp import web
from typing import Dict

from plugins.activityFile.endoints import register_custom_plugin_endpoints
from mapadroid.utils.madGlobals import WebsocketWorkerRemovedException, \
        WebsocketWorkerTimeoutException, WebsocketWorkerConnectionClosedException, \
        InternalStopWorkerException


class activityFile(mapadroid.plugins.pluginBase.Plugin):
    """activityFile plugin
    """

    def _file_path(self) -> str:
        return os.path.dirname(os.path.abspath(__file__))

    def __init__(self, subapp_to_register_to: web.Application, mad_parts: Dict):
        super().__init__(subapp_to_register_to, mad_parts)

        self._rootdir = os.path.dirname(os.path.abspath(__file__))

        self._mad = self._mad_parts
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

        # backwards compatability of activity interval setting ...
        self.activity_interval = self._pluginconfig.getint(settings, "activityinterval",
                fallback=self._pluginconfig.getint(settings, "interval", fallback=60))
        self.ip_interval = self._pluginconfig.getint(settings, "ipinterval", fallback=1800)
        self.successlog = self._pluginconfig.getboolean(settings, "successlog", fallback=True)
        self.iplog = self._pluginconfig.getboolean(settings, "iplog", fallback=False)
        self.ws_server = self._mad['ws_server']
        self.args = self._mad['args']

        self._hotlink = [
            ("activityFile Manual", "activityFile_manual", "activityFile Manual"),
        ]

        if self._pluginconfig.getboolean("plugin", "active", fallback=False):
            register_custom_plugin_endpoints(self._plugin_subapp)

            for name, link, description in self._hotlink:
                self._mad_parts['madmin'].add_plugin_hotlink(name, link.replace("/", ""),
                                                       self.pluginname, self.description, self.author, self.url,
                                                       description, self.version)


    async def _perform_operation(self):
        if not self._pluginconfig.getboolean("plugin", "active", fallback=False):
            return False

        # load your stuff now
        if not self.activity_interval == 0:
            loop = asyncio.get_event_loop()
            loop.create_task(self.activityFile())

        if not self.ip_interval == 0:
            loop = asyncio.get_event_loop()
            loop.create_task(self.saveIps())

        loop = asyncio.get_event_loop()
        loop.create_task(self.update_checker())

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


    async def update_checker(self):
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
            await asyncio.sleep(3600)


    async def send_command(self, device, command, timeout=10):
        try:
            communicator = self.ws_server.get_origin_communicator(device)
            self.logger.debug("communicator: {}".format(communicator))
            result = await communicator._Communicator__run_get_gesponse(command, timeout=timeout)
            return result
        except Exception as e:
            self.logger.warning("Sending command to {} failed with exception: {} "
                "(repr: {}) - try to gracefully stop worker!", device, e, repr(e))
            return None


    async def activityFile(self):
        self.logger.success("starting activityFile thread")
        comparedict = {}
        while True:
            devices = await self.ws_server.get_reg_origins()
            loglist = []
            for device in devices:
                communicator = self.ws_server.get_origin_communicator(device)
                entry = communicator.websocket_client_entry
                timestamp = int(entry.last_message_received_at)
                # touch file
                if timestamp > 10000:
                    if device in comparedict and timestamp - comparedict[device] > 90:
                        self.logger.success("{} recovered after {} seconds!",
                                            device, timestamp - comparedict[device])
                    path = os.path.join(self.args.file_path, str(device) + '.active')
                    tsTuple = (timestamp, timestamp)
                    try:
                        os.utime(path, tsTuple)
                    except FileNotFoundError:
                        self.logger.warning(f"FileNotFound Error for {path} - try Pathlib touch")
                        Path(path).touch()
                    loglist.append((device, datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')))
                    comparedict[device] = timestamp
            if self.successlog:
                loglist = sorted(loglist, key=lambda x: x[1], reverse=True)
                self.logger.success("touched {} devices: {}", len(loglist), loglist)
                self.logger.success("Info on {} devices total: {}", len(comparedict), comparedict)
            await asyncio.sleep(self.activity_interval)


    async def saveIps(self):
        self.logger.success("starting saveIps thread - wait 1 minute for devices to connect")
        await asyncio.sleep(60)
        while True:
            devices = await self.ws_server.get_reg_origins()
            loglist = []
            for device in devices:
                ipcommand = ("passthrough echo \"$(ifconfig | awk '/inet addr/{print substr($2,6)}' "
                            "| grep -v '127.0.0.1'),$(curl -k -s https://ifconfig.me)\"")
                ips = await self.send_command(device, ipcommand)
                if ips:
                    ips = ips.replace("[", "").replace("]", "")
                    if self.iplog:
                        self.logger.success(f"{device} got IPs: {ips}")
                    path = os.path.join(self.args.file_path, str(device) + '.ips')
                    with open(path, "w") as f:
                        f.write(f"{ips}")
            self.logger.debug(f"saveIps function sleep {self.ip_interval}")
            await asyncio.sleep(self.ip_interval)
