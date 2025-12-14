from . import crud
from .dependencies import get_current_user, require_admin
from fastapi import File, UploadFile
from datetime import datetime, timezone, timedelta
import os
import uvicorn
from fastapi import FastAPI, Request, Query, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from urllib.parse import urlencode
from fastapi.responses import FileResponse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "frontend" / "static"
TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"

port = int(os.environ.get("PORT", 8080))  # Railway sets PORT automatically

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port)

app = FastAPI()
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')
templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals["get_user"] = lambda request: getattr(request.state, "user", None)

@app.get("/favicon.ico")
async def favicon():
    return FileResponse(STATIC_DIR / "favicon.ico")

@app.get('/admin', response_class=HTMLResponse)
async def admin_page(request: Request, filter: str = Query("", alias="filter"), msg: str = Query("", alias="msg"), user=Depends(require_admin)):
    types = crud.list_item_types(filter)
    return templates.TemplateResponse('admin.html', {'request': request, 'types': types, 'filter': filter, 'msg': msg})

@app.get('/fridge', response_class=HTMLResponse)
async def fridge(request: Request, filter: str = Query("", alias="filter"), msg: str = Query("", alias="msg")):
    items = crud.list_fridge_items(filter)
    types = crud.list_item_types("")
    typesDict = {item["id"]: item for item in types}
    return templates.TemplateResponse('fridge.html', {'request': request, 'items': items, 'types': types, 'typesDict': typesDict, 'filter': filter, 'msg': msg})

@app.get('/cart', response_class=HTMLResponse)
async def cart(request: Request, filter: str = Query("", alias="filter"), msg: str = Query("", alias="msg")):
    cart = crud.list_cart_items(filter)
    types = crud.list_item_types("")
    typesDict = {item["id"]: item for item in types}
    return templates.TemplateResponse('cart.html', {'request': request, 'cart': cart, 'types': types, 'typesDict': typesDict, 'filter': filter, 'msg': msg})

@app.get('/stats', response_class=HTMLResponse)
async def stats(request: Request, filter: str = Query("", alias="filter"), start: str = Query(None), end: str = Query(None), msg: str = Query("", alias="msg")):
    if not start:
        default_start = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    else:
        default_start = start
    if not end:
        default_end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    else:
        default_end = end
    change_log = crud.list_change_log(filter, start, end)
    stats = crud.get_item_statistics(filter, start, end)
    return templates.TemplateResponse('stats.html', {'request': request,'stats': stats, 'change_log': change_log, 'filter': filter, 'default_start': default_start, 'default_end': default_end, 'msg': msg})

@app.post('/admin/item-type/create')
async def create_item_type(add_item_name: str = Form(...), add_item_desc: str = Form(...), user=Depends(require_admin)):
    err = crud.add_item_type(add_item_name, add_item_desc)
    url = prepareUrl('/admin', err, 'Item type added successfully!')
    return RedirectResponse(url, status_code=303)

@app.post('/fridge/item/create')
async def add_fridge_item(add_item_item_type_id: str = Form(...), add_item_quantity: float = Form(...), add_item_unit: str = Form(...), add_photo: UploadFile | None = File(None), add_expiry_date:str | None = Form(None), user=Depends(get_current_user)):
    err = crud.add_fridge_item(add_item_item_type_id, add_item_quantity, add_item_unit, user.get('email'), add_photo, add_expiry_date)
    url = prepareUrl('/fridge', err, 'Item successfully added to the fridge!')
    return RedirectResponse(url, status_code=303)

@app.post('/cart/item/create')
async def add_cart_item(add_item_item_type_id: str = Form(...), add_item_quantity: float = Form(...), add_item_unit: str = Form(...), user=Depends(get_current_user)):
    err = crud.add_cart_item(add_item_item_type_id, add_item_quantity, add_item_unit, user.get('email'))
    url = prepareUrl('/cart', err, 'Item successfully added to the shoping cart!')
    return RedirectResponse(url, status_code=303)

@app.post('/fridge/item/addtocart')
async def add_to_cart(item_type_id: str = Form(...), quantity: float = Form(...), unit: str = Form(...), user=Depends(get_current_user)):
    err = crud.add_cart_item(item_type_id, quantity, unit, user.get('email'))
    url = prepareUrl('/fridge', err, 'Item successfully added to the shoping cart!')
    return RedirectResponse(url, status_code=303)

@app.post('/admin/item-type/update')
async def update_item_type(item_type_id: str = Form(...), name: str = Form(...), description: str = Form(''), user=Depends(require_admin)):
    err = crud.update_item_type(item_type_id, name, description)
    url = prepareUrl('/admin', err, 'Item type modified successfully!')
    return RedirectResponse(url, status_code=303)

@app.post('/fridge/item/update')
async def update_fridge_item(item_id: str = Form(...), type_name: str = Form(...), quantity: float = Form(...), unit: str = Form(...), photo: UploadFile | None = File(None), expiry_date: str | None = Form(None), user=Depends(get_current_user)):
    
    err = crud.update_fridge_item(item_id, quantity, unit,user.get('email'), type_name, photo, expiry_date)
    url = prepareUrl('/fridge', err, 'Item successfully updated in the fridge!')
    return RedirectResponse(url, status_code=303)

@app.post('/cart/item/update')
async def update_cart_item(cart_id: str = Form(...), quantity: float = Form(...), unit: str = Form(...), user=Depends(get_current_user)):
    err = crud.update_cart_item(cart_id, quantity, unit, user.get('email'))
    url = prepareUrl('/cart', err, 'Item successfully updated in the shoping cart!')
    return RedirectResponse(url, status_code=303)

@app.post("/admin/item-type/delete")
async def delete_item_type(item_type_id: str = Form(...), user=Depends(require_admin)):
    err = crud.delete_item_type(item_type_id)
    url = prepareUrl('/admin', err, 'Item type deleted successfully!')
    return RedirectResponse(url, status_code=303)

@app.post("/fridge/item/delete")
async def delete_fridge_item(type_name: str = Form(...), item_id: str = Form(...), user=Depends(get_current_user)):
    err = crud.delete_fridge_item(item_id, user.get('email'), type_name)
    url = prepareUrl('/fridge', err, 'Item successfully removed from the fridge!')
    return RedirectResponse(url, status_code=303)

@app.post("/cart/item/delete")
async def delete_cart_item(cart_id: str = Form(...), user=Depends(get_current_user)):
    err = crud.delete_cart_item(cart_id)
    url = prepareUrl('/cart', err, 'Item successfully removed from the cart!')
    return RedirectResponse(url, status_code=303)

@app.get('/login', response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse('login.html', {'request': request})

@app.get('/logout')
async def logout():
    response = RedirectResponse(url='/login', status_code=303)
    response.delete_cookie('token')
    return response

@app.get('/',response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse('login.html', {'request': request})

@app.middleware("http")
async def add_user_to_request(request: Request, call_next):
    try:
        # Try to get user from token / session
        user = await get_current_user(request)
    except Exception:
        user = None  # not logged in or token invalid
    request.state.user = user

    response = await call_next(request)
    return response

@app.exception_handler(HTTPException)
async def auth_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        # Detect if it's an AJAX/fetch call
        if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.headers.get("accept") == "application/json":
            # Return JSON for fetch
            return JSONResponse(
                {"detail": "Not authenticated"},
                status_code=401
            )
        # Otherwise, normal page request → redirect to login
        next = "/"
        if request.url.path.startswith("/admin"):
            next = "/admin"
        elif request.url.path.startswith("/cart"):
            next = "/cart"
        return RedirectResponse(url=f"/login?next={next}", status_code=303)
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        # User logged in but lacks privileges
        return HTMLResponse(
            content="""
            <html>
                <head><title>Access Denied</title></head>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h2>🚫 Access Denied</h2>
                    <p>You do not have permission to access this page.</p>
                    <a href="/">Return to Home</a>
                </body>
            </html>
            """,
            status_code=403
        )
    raise exc

def prepareUrl(url: str, err: str, message: str):
    if not err:
        params = urlencode({"msg": message})
    else:
        params = urlencode({"msg": err})
    url = f"{url}?{params}"
    return url