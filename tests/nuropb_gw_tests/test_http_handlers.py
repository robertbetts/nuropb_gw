import urllib.parse

from tornado.httpclient import HTTPClientError

import pytest


@pytest.mark.asyncio
async def test_hello_world(web_client, web_url):
    response = await web_client.fetch(web_url)
    assert response.code == 200


@pytest.mark.asyncio
async def test_private_hello_world(web_client, web_url_private, webserver):
    with pytest.raises(HTTPClientError):
        response = await web_client.fetch(web_url_private)
        assert response.code == 401


@pytest.mark.asyncio
async def test_private_hello_auth_header(web_client, web_url_private):
    headers = {
        "Authorization": "Bearer :" + "accesstokentest1"
    }
    response = await web_client.fetch(web_url_private, headers=headers)
    assert response.code == 200
    assert response.effective_url == web_url_private
    assert response.body == b"Private Hello world"


@pytest.mark.asyncio
async def test_private_hello_auth_cookie(web_client, web_url_private):
    headers = {
        "Cookie": f"Authorization=accesstokentest1"
    }
    response = await web_client.fetch(web_url_private, headers=headers)
    assert response.code == 200
    assert response.effective_url == web_url_private
    assert response.body == b"Private Hello world"

