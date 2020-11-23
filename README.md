# mp-activityFile
MAD plugin to touch a `.active` file when there is an active connection to RGC on a device

### Description
This very simple plugin will touch a file called `$origin.active` in the folder you configured as files-folder in MAD (default: `files/` inside your MAD folder) for every device that currently has RGC connected to MAD.
Thus, you can identify a devices RGC connection status by looking at the last-modified time of the corresponding `.active` file.

This differs from the info you can get from the MADmin status page, as the status page only denotes the last time of successful data transmission from PogoDroid.

### Setup
The plugin should work out of the box. In the `plugin.ini` file, you can set the check interval in seconds and disable the logline showing all "touched" device-files with the time of the last data from RGC.
You can add a new section - where the name of the section is the status-name you set in MADs config - to configure the following values per instance (showing the default values):
```
[settings]
interval = 60
successlog = True
```
