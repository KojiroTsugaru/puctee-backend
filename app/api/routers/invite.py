from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/invite", response_class=HTMLResponse)
async def invite(request: Request, planId: str):
    """
    https://your-domain.com/invite?planId=12345
    のようにアクセスされたら、以下の HTML（テンプレート）を返す。
    """
    return templates.TemplateResponse("invite.html", {
        "request": request,
        "planId": planId,
        # App Store の自分のアプリページ URL
        "app_store_url": "https://apps.apple.com/jp/app/あなたのアプリID"
    }) 