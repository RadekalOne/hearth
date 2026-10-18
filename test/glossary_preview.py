"""Isolated loopback preview of the real app with a clearly synthetic identity.
No production token, volume, Matrix server or model/provider request is used.
"""
import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
import uvicorn
from starlette.responses import RedirectResponse, FileResponse
from starlette.routing import Route
from fastapi.routing import APIRoute

temporary = tempfile.TemporaryDirectory(prefix='hearth-glossary-preview-')
root = Path(temporary.name).resolve()
token = 'local-only-synthetic-glossary-preview'
fixture_tokens = {'fixture-author':token, **{name:'fixture-'+name for name in ['codex','kimi3','glm53','hy4','mavis']}}
os.environ.update(HEARTH_DATA_DIR=str(root), HEARTH_MEMORY_ADMIN_TOKEN='local-only-preview-admin',
                  HEARTH_HOMESERVER_URL='', HEARTH_MATRIX_TOKEN='', HEARTH_COMMONS_ENABLED='true',
                  HEARTH_COMMONS_PARTICIPANTS=','.join(fixture_tokens), HEARTH_MEMORY_COOKIE_SECURE='false')
(root/'memory-tokens.json').write_text(json.dumps(fixture_tokens),encoding='utf-8')
spec = importlib.util.spec_from_file_location('glossary_preview_app',Path(__file__).parents[1]/'mcp/memory/app.py')
memory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(memory)

def preview_auth_status():
    return {**memory.auth_status(), 'local_preview':True}
for index, route in enumerate(memory.app.router.routes):
    if getattr(route,'path','') == '/api/auth/status':
        memory.app.router.routes[index] = APIRoute('/api/auth/status',preview_auth_status,methods=['GET'])
        break

async def preview(request):
    response = RedirectResponse('/glossary?preview=1')
    response.set_cookie(memory.SESSION_COOKIE,memory.create_session('fixture-author','token',token),httponly=True,samesite='strict')
    return response

memory.app.router.routes.insert(0,Route('/preview',preview))
if os.environ.get('HEARTH_TEST_AXE_PATH'):
    async def axe_script(request):
        return FileResponse(os.environ['HEARTH_TEST_AXE_PATH'],media_type='application/javascript')
    memory.app.router.routes.insert(0,Route('/test-axe.js',axe_script))
sock = socket.socket()
sock.bind(('127.0.0.1',int(os.environ.get('GLOSSARY_PREVIEW_PORT','0'))))
port = sock.getsockname()[1]
class Server(uvicorn.Server):
    async def startup(self,sockets=None):
        await super().startup(sockets=sockets)
        print('GLOSSARY_PREVIEW='+json.dumps({'url':f'http://127.0.0.1:{port}/preview'}),flush=True)

try:
    Server(uvicorn.Config(memory.app,host='127.0.0.1',port=port,log_level='warning')).run(sockets=[sock])
finally:
    memory.chroma._system.stop()
    temporary.cleanup()
