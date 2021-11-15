from aiohttp import web
from plugins.activityFile.endoints.activityFileManualEndpoint import activityFileManualEndpoint


def register_custom_plugin_endpoints(app: web.Application):
    # Simply register any endpoints here. If you do not intend to add any views (which is discouraged) simply "pass"
    app.router.add_view('/activityFile_manual', activityFileManualEndpoint, name='activityFile_manual')
