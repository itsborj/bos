from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db import get_db
from routers.workspace import get_singleton

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/booking-url")
async def get_booking_url(db: AsyncSession = Depends(get_db)):
    ws = await get_singleton(db)
    return {"url": ws.booking_url if ws else None}


@router.get("/widget.js")
async def booking_widget_js(settings=Depends(get_settings)):
    api_base = settings.frontend_url.rstrip("/") + "/api"
    js = _WIDGET_JS_TEMPLATE.replace("__API_BASE__", api_base)
    return Response(
        content=js,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# Universal embed snippet — works on WordPress, plain HTML, Webflow, anything.
# Usage: <div data-klaroha-booking></div>
#        <script src="https://yourdomain.com/api/calendar/widget.js" async></script>
_WIDGET_JS_TEMPLATE = r"""(function () {
  'use strict';
  var API = '__API_BASE__';

  function injectStyles() {
    if (document.getElementById('klr-widget-styles')) return;
    var s = document.createElement('style');
    s.id = 'klr-widget-styles';
    s.textContent = [
      '.klr-cal-wrap{width:100%}',
      '.klr-cal-wrap iframe{border:0;width:100%;height:700px;border-radius:8px;display:block}',
      '.klr-loading{color:#6b6560;font-size:14px;padding:12px 0}',
      '.klr-unavail{color:#6b6560;font-size:14px;padding:12px 0;font-style:italic}',
    ].join('');
    document.head.appendChild(s);
  }

  function initContainer(el) {
    var loadEl = document.createElement('div');
    loadEl.className = 'klr-loading';
    loadEl.textContent = 'Loading calendar…';
    el.appendChild(loadEl);

    fetch(API + '/calendar/booking-url')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        loadEl.style.display = 'none';
        if (!data.url) {
          var msg = document.createElement('div');
          msg.className = 'klr-unavail';
          msg.textContent = 'Booking is not available at this time.';
          el.appendChild(msg);
          return;
        }
        var wrap = document.createElement('div');
        wrap.className = 'klr-cal-wrap';
        var iframe = document.createElement('iframe');
        iframe.src = data.url;
        iframe.title = 'Book a meeting';
        iframe.setAttribute('allowfullscreen', '');
        wrap.appendChild(iframe);
        el.appendChild(wrap);
      })
      .catch(function () {
        loadEl.textContent = 'Could not load the booking calendar.';
      });
  }

  function init() {
    injectStyles();
    document.querySelectorAll('[data-klaroha-booking]').forEach(function (el) {
      initContainer(el);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
"""
