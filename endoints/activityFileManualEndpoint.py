from mapadroid.plugins.endpoints.AbstractPluginEndpoint import AbstractPluginEndpoint
import aiohttp_jinja2


class activityFileManualEndpoint(AbstractPluginEndpoint):
    """
    "/activityFile_manual"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('activityFile_manual.html')
    async def get(self):
        return {"header": "activityFile Manual",
                "title": "activityFile Manual"}
